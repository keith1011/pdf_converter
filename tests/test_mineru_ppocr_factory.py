from __future__ import annotations

from ocr_pipeline.engines.mineru_layout import MineruLayoutEngine
from ocr_pipeline.engines.ppocr_text import PpocrTextEngine
from ocr_pipeline.engines.unimernet_formula import UnimernetFormulaEngine
from ocr_pipeline.factory import build_default_pipeline


def test_factory_wires_mineru_ppocr_unimernet_without_loading_weights(tmp_path):
    pipeline = build_default_pipeline(
        {
            "engines": {
                "layout": "mineru",
                "text": "ppocr",
                "formula": "unimernet",
            },
            "layout": {"device": "cuda"},
            "paths": {
                "crop_dir": str(tmp_path / "crops"),
                "output_dir": str(tmp_path / "output"),
                "pages_dir": str(tmp_path / "pages"),
            },
        }
    )

    assert isinstance(pipeline.layout_engine, MineruLayoutEngine)
    assert isinstance(pipeline.router.math_router.formula_engine, UnimernetFormulaEngine)
    assert isinstance(pipeline.router.text_router.text_engine, PpocrTextEngine)
    assert isinstance(pipeline.router.text_router.table_engine, PpocrTextEngine)
