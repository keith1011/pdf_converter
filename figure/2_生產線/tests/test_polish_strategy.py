"""Content-first Stage3 always polishes per page (PageIR requirement)."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.cli_report import WarnCollector
from ocr_pipeline.pipeline import PipelineManager


class _Layout:
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


class _Router:
    def route_page(self, blocks):
        return blocks


class _Assembler:
    def stitch(self, blocks):
        return "draft"


def test_pipeline_always_polishes_each_page_even_when_flag_false(tmp_path: Path):
    calls = {"polish": 0}

    class CountingPolisher:
        def polish(self, draft):
            calls["polish"] += 1
            return "TXT", FinalPolisher.wrap_tex("BODY"), []

        @staticmethod
        def extract_tex_body(tex):
            return FinalPolisher.extract_tex_body(tex)

        @staticmethod
        def wrap_tex(body):
            return FinalPolisher.wrap_tex(body)

    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF")
    mgr = PipelineManager(
        _Layout(),
        _Router(),
        _Assembler(),
        CountingPolisher(),
        output_dir=tmp_path / "out",
        pages_dir=tmp_path / "pages",
        nup_enabled=False,
    )
    mgr.run(pdf, single_instance_lock=False, warns=WarnCollector())
    assert calls["polish"] == 1
