from __future__ import annotations

from ocr_pipeline.engines.doclayout_yolo import DocLayoutYoloEngine
from ocr_pipeline.engines.got_formula import GotFormulaEngine
from ocr_pipeline.engines.ppocr_text import PpocrTextEngine
from ocr_pipeline.factory import build_default_pipeline


def test_factory_wires_got_ppocr_doclayout_without_loading_weights(tmp_path):
    pipeline = build_default_pipeline(
        {
            "engines": {
                "layout": "doclayout_yolo",
                "text": "ppocr",
                "formula": "got",
            },
            "layout": {"device": "cuda"},
            "paths": {
                "crop_dir": str(tmp_path / "crops"),
                "output_dir": str(tmp_path / "output"),
                "pages_dir": str(tmp_path / "pages"),
            },
        }
    )

    assert isinstance(pipeline.layout_engine, DocLayoutYoloEngine)
    assert isinstance(pipeline.router.math_router.formula_engine, GotFormulaEngine)
    assert isinstance(pipeline.router.text_router.text_engine, PpocrTextEngine)
    assert isinstance(pipeline.router.text_router.table_engine, PpocrTextEngine)
