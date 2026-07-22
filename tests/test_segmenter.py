"""TDD T2: stitch-then-segment with page-level synthetic ids (3B/6A)."""

from __future__ import annotations

from ocr_pipeline.models import BBox, SegmentKind
from ocr_pipeline.segmenter import segment_stitched_page


def test_segment_strips_image_conversion_meta_and_keeps_math():
    stitched = (
        "以下是將圖片中的表格轉換為 LaTeX 表格的結果：\n"
        "設 x 為得分。\n"
        r"$x=60$"
        "\n"
    )
    page = segment_stitched_page(
        page_index=1,
        stitched_text=stitched,
        page_bbox=BBox(0, 0, 800, 1100),
    )
    assert page.page_index == 1
    kinds = [s.kind for s in page.segments]
    texts = [s.text for s in page.segments]
    assert SegmentKind.MATH in kinds
    assert "x=60" in texts
    assert all("將圖片" not in s.text for s in page.segments)
    assert all(s.source_block_id == "p1_stitched" for s in page.segments)
    assert all(s.bbox.as_int_tuple() == (0, 0, 800, 1100) for s in page.segments)


def test_segment_treats_undelimited_frac_line_as_math():
    page = segment_stitched_page(
        page_index=2,
        stitched_text=r"\frac{a}{b}=1",
        page_bbox=BBox(0, 0, 10, 10),
    )
    assert len(page.segments) == 1
    assert page.segments[0].kind is SegmentKind.MATH
    assert page.segments[0].text == r"\frac{a}{b}=1"
    assert page.segments[0].source_block_id == "p2_stitched"


def test_segment_linearizes_markdown_table_and_html_breaks():
    page = segment_stitched_page(
        page_index=3,
        stitched_text=(
            "| 解答 | 分數 |\n"
            "| --- | :---: |\n"
            "| 設 $x=1$<br>所以 $y=2$ | 1M |"
        ),
        page_bbox=BBox(0, 0, 10, 10),
    )

    texts = [segment.text for segment in page.segments]
    assert "x=1" in texts
    assert "y=2" in texts
    assert "設" in texts
    assert "所以" in texts
    assert "1M" in texts
    assert all("|" not in text for text in texts)
    assert all("<br" not in text.lower() for text in texts)
    assert not any(set(text) <= {"-", ":"} for text in texts)


def test_segment_linearizes_latex_layout_environments():
    page = segment_stitched_page(
        page_index=4,
        stitched_text=(
            "\\begin{itemize}\n"
            "\\item 1M\n"
            "\\end{itemize}\n"
            "\\begin{align*}\n"
            "&4a + 5b - 7 = 8b \\\\\n"
            "&b = \\frac{4a-7}{3}\n"
            "\\end{align*}"
        ),
        page_bbox=BBox(0, 0, 10, 10),
    )

    assert [(segment.kind, segment.text) for segment in page.segments] == [
        (SegmentKind.MARK_NOTE, "1M"),
        (SegmentKind.MATH, "4a + 5b - 7 = 8b"),
        (SegmentKind.MATH, r"b = \frac{4a-7}{3}"),
    ]
