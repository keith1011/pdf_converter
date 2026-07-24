"""Regression tests for the content-first PipelineManager data flow."""

from __future__ import annotations

import json
from pathlib import Path

from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.cli_report import WarnCollector
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
    )

    result = manager.run(pdf, warns=WarnCollector())

    assert "POLISHED BODY" in result.txt
    assert "| --- |" not in result.txt
    assert result.pages[0].tex
    data = json.loads(result.pageir_path.read_text(encoding="utf-8"))
    texts = [segment["text"] for segment in data["pages"][0]["segments"]]
    assert "POLISHED BODY" in texts
    assert not any("| --- |" in text for text in texts)
