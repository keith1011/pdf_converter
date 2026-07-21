"""Build a wired PipelineManager from config dict / defaults."""

from __future__ import annotations

from pathlib import Path

import yaml

from .assemble import DraftAssembler, FinalPolisher
from .layout import LayoutAnalyzer
from .pipeline import PipelineManager
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

    vlm = build_vlm_client(cfg)
    backend = str(vlm_cfg.get("backend", "qwen")).lower()
    text_label = "Qwen2.5-VL" if backend != "glm" else "GLM-4.6V-Flash"

    layout = LayoutAnalyzer(
        dpi=int(layout_cfg.get("dpi", 200)),
        device=str(layout_cfg.get("device", "cuda")),
        force_backend=str(layout_cfg.get("force_backend", "")),
    )
    math = MathRouter(engine=str(cfg.get("math", {}).get("engine", "mineru")), glm_fallback=vlm)
    text = TextRouter(vlm=vlm, model_name=text_label)
    crop_dir = Path(paths.get("crop_dir", "output/crops"))
    router = DynamicRouter(math, text, crop_dir=crop_dir)

    return PipelineManager(
        layout=layout,
        router=router,
        assembler=DraftAssembler(),
        polisher=FinalPolisher(vlm),
        output_dir=Path(paths.get("output_dir", "output")),
        pages_dir=Path(paths.get("pages_dir", "data/pdf_pages")),
    )
