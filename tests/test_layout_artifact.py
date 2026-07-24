"""LayoutArtifact persist / resume (Phase 2.5b / 2.8)."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.layout_artifact import (
    layout_artifact_path,
    load_layout_artifact,
    save_layout_artifact,
)
from ocr_pipeline.models import BBox, BlockType, LayoutBlock, PageResult


def _sample_page(tmp_path: Path) -> PageResult:
    image = tmp_path / "page_001.png"
    image.write_bytes(b"png")
    block = LayoutBlock(
        block_id="p1_b0",
        block_type=BlockType.TEXT,
        bbox=BBox(1, 2, 30, 40),
        order=0,
        page=1,
        image_path=image,
        raw_text="",
    )
    return PageResult(page=1, image_path=image, blocks=[block])


def test_save_and_load_layout_artifact_roundtrip(tmp_path: Path):
    page = _sample_page(tmp_path)
    path = layout_artifact_path(tmp_path)
    save_layout_artifact(path, source="demo", pdf_path=tmp_path / "demo.pdf", pages=[page])

    loaded = load_layout_artifact(path)
    assert len(loaded) == 1
    assert loaded[0].page == 1
    assert loaded[0].blocks[0].block_id == "p1_b0"
    assert loaded[0].blocks[0].block_type == BlockType.TEXT
    assert loaded[0].blocks[0].bbox.as_int_tuple() == (1, 2, 30, 40)


def test_pipeline_writes_and_reuses_layout_artifact(tmp_path: Path):
    from ocr_pipeline.assemble import FinalPolisher
    from ocr_pipeline.cli_report import WarnCollector
    from ocr_pipeline.pipeline import PipelineManager

    calls = {"analyze": 0}

    class Layout:
        _backend = "surya"

        def pdf_to_images(self, pdf_path, out_dir, *, limit=0):
            out_dir.mkdir(parents=True, exist_ok=True)
            page = out_dir / "page_001.png"
            page.write_bytes(b"x")
            return [page]

        def analyze_page(self, image_path, page):
            calls["analyze"] += 1
            return [
                LayoutBlock(
                    block_id=f"p{page}_b0",
                    block_type=BlockType.TEXT,
                    bbox=BBox(0, 0, 10, 10),
                    order=0,
                    page=page,
                    image_path=image_path,
                )
            ]

        def release(self):
            pass

    class Router:
        def route_page(self, blocks):
            for b in blocks:
                b.raw_text = "hello"
            return blocks

    class Assembler:
        def stitch(self, blocks):
            return "hello"

    class Polisher:
        def polish(self, draft):
            return "TXT", FinalPolisher.wrap_tex("BODY"), []

        @staticmethod
        def extract_tex_body(tex):
            return FinalPolisher.extract_tex_body(tex)

        @staticmethod
        def wrap_tex(body):
            return FinalPolisher.wrap_tex(body)

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF")
    pages_dir = tmp_path / "pages"
    output = tmp_path / "output"
    mgr = PipelineManager(
        Layout(),
        Router(),
        Assembler(),
        Polisher(),
        output_dir=output,
        pages_dir=pages_dir,
    )

    mgr.run(pdf, overwrite=True, single_instance_lock=False, warns=WarnCollector())
    artifact = layout_artifact_path(pages_dir / "doc")
    assert artifact.exists()
    assert calls["analyze"] == 1

    mgr.run(
        pdf,
        overwrite=False,
        reuse_layout=True,
        single_instance_lock=False,
        warns=WarnCollector(),
    )
    assert calls["analyze"] == 1  # Surya not re-run
