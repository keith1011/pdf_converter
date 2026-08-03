
from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.cli_report import WarnCollector
from ocr_pipeline.engines.ppocr_text import PpocrTextEngine
from ocr_pipeline.engines.paddleocr_vl_text import PaddleOcrVlTextEngine
from ocr_pipeline.factory import build_default_pipeline
from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.pipeline import PipelineManager


class ImageSource:
    def pdf_to_images(self, pdf_path, out_dir, *, limit=0):
        out_dir.mkdir(parents=True, exist_ok=True)
        page = out_dir / "page_001.png"
        page.write_bytes(b"x")
        return [page]


class LayoutEngine:
    def analyze(self, image_path, page):
        return [
            LayoutBlock("b0", BlockType.TEXT, BBox(0, 0, 10, 10), 0, page, image_path)
        ]

    def release(self):
        pass


class Router:
    def route_page(self, blocks):
        for block in blocks:
            block.raw_text = "hi"
        return blocks


class Assembler:
    def stitch(self, blocks):
        return "hi"


class BoomPolisher:
    def polish(self, draft):
        raise AssertionError("skip_polish must not call polish")

    @staticmethod
    def extract_tex_body(tex):
        return FinalPolisher.extract_tex_body(tex)

    @staticmethod
    def wrap_tex(body):
        return FinalPolisher.wrap_tex(body)


def test_skip_polish_uses_draft_and_tags_output(tmp_path, capsys):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    mgr = PipelineManager(
        layout=ImageSource(),
        layout_engine=LayoutEngine(),
        router=Router(),
        assembler=Assembler(),
        polisher=BoomPolisher(),
        output_dir=tmp_path / "out",
        pages_dir=tmp_path / "pages",
        nup_enabled=False,
    )

    result = mgr.run(
        pdf,
        skip_polish=True,
        single_instance_lock=False,
        output_tag="t",
        warns=WarnCollector(),
    )

    assert result.tex_path is not None
    assert result.tex_path.name == "a.t.tex"
    assert "hi" in result.txt
    assert "TIMING: layout=" in capsys.readouterr().out


def test_factory_builds_ppocr_text_engines():
    manager = build_default_pipeline({"engines": {"text": "ppocr"}})

    assert isinstance(manager.router.text_router.text_engine, PpocrTextEngine)
    assert isinstance(manager.router.text_router.table_engine, PpocrTextEngine)


def test_factory_builds_paddleocr_vl_text_engines():
    manager = build_default_pipeline({"engines": {"text": "paddleocr_vl"}})

    assert isinstance(manager.router.text_router.text_engine, PaddleOcrVlTextEngine)
    assert isinstance(manager.router.text_router.table_engine, PaddleOcrVlTextEngine)
    assert manager.polisher.mcq_stage3 == "paddle_sanitize"


def test_factory_wires_skip_figures_from_pipeline_config():
    on = build_default_pipeline({"pipeline": {"skip_figures": True}})
    off = build_default_pipeline({"pipeline": {"skip_figures": False}})
    assert on.router.skip_figures is True
    assert off.router.skip_figures is False


def test_factory_wires_extract_figures_from_pipeline_config():
    default = build_default_pipeline({})
    off = build_default_pipeline({"pipeline": {"extract_figures": False}})
    assert default.extract_figures is True
    assert off.extract_figures is False
