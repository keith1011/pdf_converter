from __future__ import annotations

import time
from pathlib import Path

from ocr_pipeline.engines.base import EngineError, FormulaEngine, LayoutEngine, TextEngine
from ocr_pipeline.engines.surya_layout import SuryaLayoutEngine
from ocr_pipeline.engines.timing import StageTimer
from ocr_pipeline.engines.vlm_formula import VlmFormulaEngine
from ocr_pipeline.engines.vlm_text import VlmTextEngine
from ocr_pipeline.models import BlockType, BBox, LayoutBlock


class FakeLayout:
    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]:
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

    def release(self) -> None:
        return None


class FakeText:
    def ocr(self, crop_path: Path) -> str:
        return "hello $x$"


class FakeFormula:
    def ocr(self, crop_path: Path) -> str:
        return "$$\nx\n$$"


def test_fakes_satisfy_protocols():
    assert isinstance(FakeLayout(), LayoutEngine)
    assert isinstance(FakeText(), TextEngine)
    assert isinstance(FakeFormula(), FormulaEngine)


def test_engine_error_is_runtime_error():
    err = EngineError("missing paddleocr")
    assert isinstance(err, RuntimeError)
    assert "paddleocr" in str(err)


def test_stage_timer_records_seconds():
    t = StageTimer()
    with t.section("layout"):
        time.sleep(0.01)
    d = t.as_dict()
    assert d["layout"] >= 0.01
    assert "total" in d


def test_surya_layout_engine_delegates(tmp_path):
    calls = {}

    class FakeAnalyzer:
        def analyze_page(self, image_path, page):
            calls["page"] = page
            return []

        def release(self):
            calls["released"] = True

    eng = SuryaLayoutEngine(FakeAnalyzer())
    img = tmp_path / "p.png"
    img.write_bytes(b"x")
    assert eng.analyze(img, 1) == []
    eng.release()
    assert calls["released"] is True


def test_vlm_text_engine_calls_generate(tmp_path):
    class FakeVlm:
        def generate(self, prompt, image_path=None, *, max_new_tokens=None):
            return "正文"

    crop = tmp_path / "c.png"
    crop.write_bytes(b"x")
    assert VlmTextEngine(FakeVlm()).ocr(crop) == "正文"
