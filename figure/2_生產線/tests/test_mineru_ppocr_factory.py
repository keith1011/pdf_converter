from __future__ import annotations

from ocr_pipeline.engines.mineru_layout import MineruLayoutEngine
from ocr_pipeline.engines.ppocr_text import PpocrTextEngine
from ocr_pipeline.engines.unimernet_formula import UnimernetFormulaEngine
from ocr_pipeline.engines.vlm_formula import VlmFormulaEngine
from ocr_pipeline.engines.vlm_text import VlmTextEngine
from ocr_pipeline.factory import build_default_pipeline
from ocr_pipeline.vlm_client import QwenVlClient


def test_factory_wires_trunk_mineru_qwen_qwen_without_loading_weights(tmp_path):
    """Trunk lock 2026-07-24: layout=mineru, text=vlm, formula=vlm → Qwen polish."""
    pipeline = build_default_pipeline(
        {
            "engines": {
                "layout": "mineru",
                "text": "vlm",
                "formula": "vlm",
            },
            "vlm": {
                "backend": "qwen",
                "model_name": "Qwen/Qwen2.5-VL-7B-Instruct",
                "load_in_4bit": True,
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
    assert isinstance(pipeline.router.text_router.text_engine, VlmTextEngine)
    assert isinstance(pipeline.router.math_router.formula_engine, VlmFormulaEngine)
    assert isinstance(pipeline.polisher.vlm, QwenVlClient)


def test_factory_default_engines_match_trunk_when_omitted(tmp_path):
    pipeline = build_default_pipeline(
        {
            "vlm": {"backend": "qwen"},
            "paths": {
                "crop_dir": str(tmp_path / "crops"),
                "output_dir": str(tmp_path / "output"),
                "pages_dir": str(tmp_path / "pages"),
            },
        }
    )
    assert isinstance(pipeline.layout_engine, MineruLayoutEngine)
    assert isinstance(pipeline.router.text_router.text_engine, VlmTextEngine)
    assert isinstance(pipeline.router.math_router.formula_engine, VlmFormulaEngine)


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
