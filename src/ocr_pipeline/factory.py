"""Build a wired PipelineManager from config dict / defaults."""

from __future__ import annotations

from pathlib import Path

import yaml

from .assemble import DraftAssembler, FinalPolisher
from .engines.base import EngineError
from .engines.ppocr_text import PpocrTextEngine
from .engines.surya_layout import SuryaLayoutEngine
from .engines.vlm_formula import VlmFormulaEngine
from .engines.vlm_text import VlmTextEngine
from .layout import LayoutAnalyzer
from .pipeline import PipelineManager
from .prompts import TABLE_ROUTER_PROMPT
from .routers import DynamicRouter, MathRouter, TextRouter
from .vlm_client import build_vlm_client


def load_ocr_config(path: Path | None = None) -> dict:
    cfg_path = path or Path("config/ocr_pipeline.yaml")
    if not cfg_path.exists():
        return {}
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_default_pipeline(cfg: dict | None = None) -> PipelineManager:
    cfg = cfg or load_ocr_config()
    layout_cfg = cfg.get("layout", {})
    paths = cfg.get("paths", {})
    vlm_cfg = cfg.get("vlm") or {}
    engines_cfg = cfg.get("engines") or {}

    vlm = build_vlm_client(cfg)
    backend = str(vlm_cfg.get("backend", "qwen")).lower()
    text_label = "Qwen2.5-VL" if backend != "glm" else "GLM-4.6V-Flash"
    polish_tokens = int(vlm_cfg.get("max_new_tokens", 2048))
    route_tokens = int(vlm_cfg.get("max_new_tokens_route", min(1024, polish_tokens)))

    layout_name = str(engines_cfg.get("layout", "surya")).lower()
    text_name = str(engines_cfg.get("text", "vlm")).lower()
    formula_name = str(engines_cfg.get("formula", "vlm")).lower()
    if layout_name != "surya":
        raise EngineError(f"Unknown layout engine: {layout_name}")
    if text_name not in {"vlm", "ppocr"}:
        raise EngineError(f"Unknown text engine: {text_name}")
    if formula_name != "vlm":
        raise EngineError(f"Unknown formula engine: {formula_name}")

    layout = LayoutAnalyzer(
        dpi=int(layout_cfg.get("dpi", 200)),
        device=str(layout_cfg.get("device", "cuda")),
        force_backend=str(layout_cfg.get("force_backend", "")),
    )
    math = MathRouter(
        formula_engine=VlmFormulaEngine(vlm, max_new_tokens=route_tokens),
        max_new_tokens=route_tokens,
    )
    if text_name == "ppocr":
        text_engine = PpocrTextEngine()
        table_engine = PpocrTextEngine()
    else:
        text_engine = VlmTextEngine(vlm, max_new_tokens=route_tokens)
        table_engine = VlmTextEngine(
            vlm, max_new_tokens=route_tokens, prompt=TABLE_ROUTER_PROMPT
        )
    text = TextRouter(
        model_name=text_label,
        text_engine=text_engine,
        table_engine=table_engine,
        max_new_tokens=route_tokens,
    )
    crop_dir = Path(paths.get("crop_dir", "output/crops"))
    router = DynamicRouter(math, text, crop_dir=crop_dir)

    return PipelineManager(
        layout=layout,
        layout_engine=SuryaLayoutEngine(layout),
        router=router,
        assembler=DraftAssembler(),
        polisher=FinalPolisher(vlm),
        output_dir=Path(paths.get("output_dir", "output")),
        pages_dir=Path(paths.get("pages_dir", "data/pdf_pages")),
    )
