"""TDD T4: linear render + integrity apply + pageir.json (no VLM)."""

from __future__ import annotations

import json
from pathlib import Path

from ocr_pipeline.content_first import (
    apply_integrity_to_page,
    render_page_ir,
    write_pageir_json,
)
from ocr_pipeline.models import (
    BBox,
    ContentSegment,
    IntegrityStatus,
    PageIR,
    SegmentKind,
)


def test_render_page_ir_linear_tex_and_txt():
    page = PageIR(
        page_index=1,
        segments=[
            ContentSegment(
                kind=SegmentKind.PROSE,
                text="設 x 為得分。",
                source_block_id="p1_stitched",
                bbox=BBox(0, 0, 10, 10),
            ),
            ContentSegment(
                kind=SegmentKind.MATH,
                text=r"x=60",
                source_block_id="p1_stitched",
                bbox=BBox(0, 0, 10, 10),
            ),
            ContentSegment(
                kind=SegmentKind.MARK_NOTE,
                text="1M+1A",
                source_block_id="p1_stitched",
                bbox=BBox(0, 0, 10, 10),
            ),
        ],
    )
    txt, tex_body = render_page_ir(page)
    assert "設 x 為得分。" in txt
    assert "$x=60$" in txt
    assert "(分註: 1M+1A)" in txt
    assert "$x=60$" in tex_body
    assert "(分註: 1M+1A)" in tex_body
    assert "tabular" not in tex_body


def test_apply_integrity_repairs_feac_on_math_segment():
    page = PageIR(
        page_index=1,
        segments=[
            ContentSegment(
                kind=SegmentKind.MATH,
                text=r"\feac{1}{6}",
                source_block_id="p1_stitched",
                bbox=BBox(0, 0, 1, 1),
            )
        ],
    )
    out, warns = apply_integrity_to_page(page)
    assert out.segments[0].text == r"\frac{1}{6}"
    assert out.segments[0].integrity is IntegrityStatus.REPAIRED
    assert warns


def test_write_pageir_json(tmp_path: Path):
    pages = [
        PageIR(
            page_index=1,
            segments=[
                ContentSegment(
                    kind=SegmentKind.PROSE,
                    text="hi",
                    source_block_id="p1_stitched",
                    bbox=BBox(0, 0, 100, 200),
                )
            ],
        )
    ]
    path = tmp_path / "demo.pageir.json"
    write_pageir_json(path, pages)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["pages"][0]["page_index"] == 1
    assert data["pages"][0]["segments"][0]["text"] == "hi"
    assert data["pages"][0]["segments"][0]["source_block_id"] == "p1_stitched"


def test_pipeline_writes_pageir_after_content_first(tmp_path: Path):
    from ocr_pipeline.assemble import FinalPolisher
    from ocr_pipeline.content_first import finalize_content_first

    page_drafts = [
        (1, "Let x be score.\n$x=60$\n", BBox(0, 0, 1000, 1000)),
        (2, r"\feac{1}{6}", BBox(0, 0, 1000, 1000)),
    ]

    full_txt, full_tex, txt_path, tex_path, pageir_path, warnings = finalize_content_first(
        source="demo",
        output_dir=tmp_path,
        page_drafts=page_drafts,
        wrap_tex_fn=FinalPolisher.wrap_tex,
    )

    assert txt_path.exists() and tex_path.exists() and pageir_path.exists()
    assert txt_path.read_text(encoding="utf-8") == full_txt
    assert "$x=60$" in full_txt
    assert r"$\frac{1}{6}$" in full_txt
    assert r"\documentclass" in full_tex
    assert r"\begin{document}" in full_tex
    data = json.loads(pageir_path.read_text(encoding="utf-8"))
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page_index"] == 1
    assert data["pages"][1]["page_index"] == 2
    math_seg = next(s for s in data["pages"][1]["segments"] if s["kind"] == "math")
    assert math_seg["text"] == r"\frac{1}{6}"
    assert math_seg["integrity"] == "repaired"
    assert warnings


def test_render_figure_as_caption_stub():
    page = PageIR(
        page_index=1,
        segments=[
            ContentSegment(
                kind=SegmentKind.FIGURE,
                text="圓形面積示意圖",
                source_block_id="p001_b012",
                bbox=BBox(0, 0, 10, 10),
                crop_relpath="figures/p001_b012.png",
            )
        ],
    )
    txt, tex_body = render_page_ir(page)
    assert txt == "(圖: 圓形面積示意圖)"
    assert tex_body == "(圖: 圓形面積示意圖)"


def test_write_pageir_json_includes_crop_relpath(tmp_path: Path):
    pages = [
        PageIR(
            page_index=1,
            segments=[
                ContentSegment(
                    kind=SegmentKind.FIGURE,
                    text="示意圖",
                    source_block_id="p001_b012",
                    bbox=BBox(0, 0, 10, 10),
                    crop_relpath="figures/p001_b012.png",
                )
            ],
        )
    ]
    path = tmp_path / "demo.pageir.json"
    write_pageir_json(path, pages)
    data = json.loads(path.read_text(encoding="utf-8"))
    seg = data["pages"][0]["segments"][0]
    assert seg["kind"] == "figure"
    assert seg["crop_relpath"] == "figures/p001_b012.png"


def test_finalize_merges_figure_segments(tmp_path: Path):
    from ocr_pipeline.content_first import finalize_content_first

    def wrap(body: str) -> str:
        return f"\\documentclass{{ctexart}}\\begin{{document}}{body}\\end{{document}}"

    fig = ContentSegment(
        kind=SegmentKind.FIGURE,
        text="示意圖",
        source_block_id="p001_b012",
        bbox=BBox(0, 0, 10, 10),
        crop_relpath="figures/p001_b012.png",
    )
    full_txt, _, _, _, pageir_path, _ = finalize_content_first(
        source="demo",
        output_dir=tmp_path,
        page_drafts=[(1, "正文一行", BBox(0, 0, 100, 100))],
        wrap_tex_fn=wrap,
        figure_segments_by_page={1: [fig]},
    )
    assert "(圖: 示意圖)" in full_txt
    data = json.loads(pageir_path.read_text(encoding="utf-8"))
    kinds = [s["kind"] for s in data["pages"][0]["segments"]]
    assert "figure" in kinds


def test_finalize_strips_tabular_chrome_from_polished_draft(tmp_path: Path):
    from ocr_pipeline.assemble import FinalPolisher
    from ocr_pipeline.content_first import finalize_content_first

    polished_like = (
        r"$\begin{tabular}{|c|c|c|}$$\hline$$解 & 分 & 備註 \\$$\hline$"
        r"設 $x=60$ & 1A \\"
        r"$$\hline$$\end{tabular}$"
    )
    _txt, full_tex, _tp, tex_path, _pp, _w = finalize_content_first(
        source="tab",
        output_dir=tmp_path,
        page_drafts=[(1, polished_like, BBox(0, 0, 100, 100))],
        wrap_tex_fn=FinalPolisher.wrap_tex,
    )
    body = tex_path.read_text(encoding="utf-8")
    assert body == full_tex
    assert "tabular" not in body.lower()
    assert "hline" not in body.lower()
    assert "$x=60$" in body
    assert "1A" in body
