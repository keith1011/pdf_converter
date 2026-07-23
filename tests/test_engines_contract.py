from __future__ import annotations

from pathlib import Path

from ocr_pipeline.engines.base import EngineError, FormulaEngine, LayoutEngine, TextEngine
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
