"""Regression tests for the content-first PipelineManager data flow."""

from __future__ import annotations

import json
from pathlib import Path

from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.cli_report import WarnCollector
from ocr_pipeline.models import BBox, BlockType, ContentSegment, LayoutBlock, SegmentKind
from ocr_pipeline.pipeline import PipelineManager


class _OnePageLayout:
    _backend = "surya"

    def pdf_to_images(self, pdf_path, out_dir, *, limit=0):
        out_dir.mkdir(parents=True, exist_ok=True)
        page = out_dir / "page_001.png"
        page.write_bytes(b"x")
        return [page]

    def analyze_page(self, image_path, page):
        return []

    def release(self):
        pass


class _IdentityRouter:
    def route_page(self, blocks):
        return blocks


class _MarkdownAssembler:
    def stitch(self, blocks):
        return "| 解 | 分 |\n| --- | --- |\n| $x=1$ | 1M |"


class _LinearPolisher:
    vlm = object()

    def polish(self, draft):
        return "POLISHED TXT", FinalPolisher.wrap_tex("POLISHED BODY\n$x=1$"), []

    @staticmethod
    def extract_tex_body(tex):
        return FinalPolisher.extract_tex_body(tex)

    @staticmethod
    def wrap_tex(body):
        return FinalPolisher.wrap_tex(body)


def test_single_short_page_pageir_uses_polished_body_not_stage2_markdown(tmp_path: Path):
    pdf = tmp_path / "one.pdf"
    pdf.write_bytes(b"%PDF")
    output = tmp_path / "output"
    manager = PipelineManager(
        _OnePageLayout(),
        _IdentityRouter(),
        _MarkdownAssembler(),
        _LinearPolisher(),
        output_dir=output,
        pages_dir=tmp_path / "pages",
        nup_enabled=False,
    )

    result = manager.run(pdf, warns=WarnCollector())

    assert "POLISHED BODY" in result.txt
    assert "| --- |" not in result.txt
    assert result.pages[0].tex
    data = json.loads(result.pageir_path.read_text(encoding="utf-8"))
    texts = [segment["text"] for segment in data["pages"][0]["segments"]]
    assert "POLISHED BODY" in texts
    assert not any("| --- |" in text for text in texts)


def test_pipeline_exports_figures_and_merges_them_into_pageir(tmp_path: Path, monkeypatch):
    class _FigureLayout(_OnePageLayout):
        def analyze_page(self, image_path, page):
            return [
                LayoutBlock(
                    "p001_b000",
                    BlockType.FIGURE,
                    BBox(0, 0, 10, 10),
                    0,
                    page,
                    image_path,
                )
            ]

    captured = {}

    def fake_export_figures(*, blocks, figures_dir, vlm, max_new_tokens=128):
        captured["blocks"] = blocks
        captured["figures_dir"] = figures_dir
        return (
            [
                ContentSegment(
                    kind=SegmentKind.FIGURE,
                    text="圖說",
                    source_block_id="p001_b000",
                    bbox=BBox(0, 0, 10, 10),
                    crop_relpath="figures/p001_b000.png",
                )
            ],
            [],
        )

    monkeypatch.setattr("ocr_pipeline.figure_export.export_figures", fake_export_figures)
    pdf = tmp_path / "one.pdf"
    pdf.write_bytes(b"%PDF")
    output = tmp_path / "output"
    manager = PipelineManager(
        _FigureLayout(),
        _IdentityRouter(),
        _MarkdownAssembler(),
        _LinearPolisher(),
        output_dir=output,
        pages_dir=tmp_path / "pages",
        nup_enabled=False,
    )

    result = manager.run(pdf, warns=WarnCollector())

    assert captured["figures_dir"] == output / "one" / "figures"
    assert captured["blocks"][0].block_id == "p001_b000"
    assert "(圖: 圖說)" in result.txt
    data = json.loads(result.pageir_path.read_text(encoding="utf-8"))
    assert data["pages"][0]["segments"][-1]["kind"] == "figure"
