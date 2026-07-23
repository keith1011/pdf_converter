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


def test_segment_strips_dollar_wrapped_tabular_chrome():
    """Regression: polish emits $\\begin{tabular}$/$\\hline$ → must not stay math."""
    stitched = (
        r"$\begin{table}[h]$"
        "\n"
        r"$\begin{tabular}{|c|c|c|}$$\hline$$解 & 分 & 備註 \\$$\hline$"
        r"6. (a) 該書的售價 &$x=300$& 1M\\"
        r"$$\hline$$\end{tabular}$"
        "\n"
        r"$\end{table}$"
    )
    page = segment_stitched_page(
        page_index=5,
        stitched_text=stitched,
        page_bbox=BBox(0, 0, 10, 10),
    )
    joined = "\n".join(s.text for s in page.segments)
    assert "tabular" not in joined.lower()
    assert "hline" not in joined.lower()
    assert r"\begin{table}" not in joined
    assert "解" in joined
    assert "x=300" in [s.text for s in page.segments]
    assert any(s.kind is SegmentKind.MARK_NOTE and s.text == "1M" for s in page.segments)
    assert all(
        "tabular" not in s.text.lower() and "hline" not in s.text.lower()
        for s in page.segments
    )


def test_segment_collapses_display_dollars_and_strips_markdown_fence():
    stitched = (
        "```markdown\n"
        "解\n"
        r"$$\frac{a}{b}=1$"
        "\n"
        r"$x=2$$"
        "\n"
        "```\n"
    )
    page = segment_stitched_page(
        page_index=6,
        stitched_text=stitched,
        page_bbox=BBox(0, 0, 10, 10),
    )
    texts = [s.text for s in page.segments]
    joined = "\n".join(texts)
    assert "```" not in joined
    assert "markdown" not in joined.lower()
    assert r"\frac{a}{b}=1" in texts
    assert "x=2" in texts
    assert all("$$" not in s.text for s in page.segments)


def test_segment_keeps_currency_dollar_inside_math():
    page = segment_stitched_page(
        page_index=7,
        stitched_text=r"$=250(1+20\%)=\$300$",
        page_bbox=BBox(0, 0, 10, 10),
    )
    assert len(page.segments) == 1
    assert page.segments[0].kind is SegmentKind.MATH
    assert r"\$300" in page.segments[0].text
    assert not page.segments[0].text.startswith("$")


def test_segment_splits_cjk_out_of_math():
    page = segment_stitched_page(
        page_index=8,
        stitched_text=r"$\triangle BGE$是一直角三角形。$",
        page_bbox=BBox(0, 0, 10, 10),
    )
    kinds_texts = [(s.kind, s.text) for s in page.segments]
    assert (SegmentKind.MATH, r"\triangle BGE") in kinds_texts
    assert any(
        s.kind is SegmentKind.PROSE and "直角三角形" in s.text for s in page.segments
    )
    assert all(s.text.count("$") == 0 for s in page.segments)


def test_segment_drops_marking_junk_frac_with_cjk():
    page = segment_stitched_page(
        page_index=9,
        stitched_text=r"$\frac{正方形性質}{-}$" + "\n" + r"$\frac{-}{-}$" + "\n$x=1$\n",
        page_bbox=BBox(0, 0, 10, 10),
    )
    joined = "\n".join(s.text for s in page.segments)
    assert "正方形性質" not in joined or r"\frac" not in joined
    assert r"\frac{-}{-}" not in joined
    assert any(s.kind is SegmentKind.MATH and "x=1" in s.text for s in page.segments)


def test_segment_does_not_mathify_end_document():
    page = segment_stitched_page(
        page_index=10,
        stitched_text="正文\n\\end{document}\n更多\n",
        page_bbox=BBox(0, 0, 10, 10),
    )
    texts = [s.text for s in page.segments]
    assert all("end{document}" not in t for t in texts)
    assert "正文" in texts and "更多" in texts
