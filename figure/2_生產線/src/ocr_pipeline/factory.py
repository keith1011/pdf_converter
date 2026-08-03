"""Build a wired PipelineManager from config dict / defaults."""

from __future__ import annotations

from pathlib import Path

import yaml

from .assemble import DraftAssembler, FinalPolisher
from .dse_mcq_layout_engine import DseMcqLayoutEngine
from .dse_mcq_profile import default_math_cp_p2_path, load_mcq_profile
from .engines.base import EngineError
from .engines.doclayout_yolo import DocLayoutYoloEngine
from .engines.got_formula import GotFormulaEngine
from .engines.mineru_layout import MineruLayoutEngine
from .engines.paddleocr_vl_text import PaddleOcrVlTextEngine
from .engines.ppocr_text import PpocrTextEngine
from .engines.surya_layout import SuryaLayoutEngine
from .engines.unimernet_formula import UnimernetFormulaEngine
from .engines.vlm_formula import VlmFormulaEngine
from .engines.vlm_text import VlmTextEngine
from .layout import LayoutAnalyzer
from .pipeline import PipelineManager
from .prompts import TABLE_ROUTER_PROMPT
from .routers import DynamicRouter, MathRouter, TextRouter
from .vlm_client import build_mcq_structured_client, build_vlm_client

_MCQ_STAGE3_DEFAULT = "sanitize"


def load_ocr_config(path: Path | None = None) -> dict:
    cfg_path = path or Path("2_生產線/config/ocr_pipeline.yaml")
    if not cfg_path.exists():
        return {}
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_default_pipeline(
    cfg: dict | None = None, *, dse_mcq: bool = False
) -> PipelineManager:
    cfg = cfg or load_ocr_config()
    layout_cfg = cfg.get("layout", {})
    paths = cfg.get("paths", {})
    vlm_cfg = cfg.get("vlm") or {}
    engines_cfg = cfg.get("engines") or {}

    vlm = build_vlm_client(cfg)
    model_name = str(vlm_cfg.get("model_name", "")).lower()
    if "qwen3-vl" in model_name:
        text_label = "Qwen3-VL"
    elif "qwen2.5-vl" in model_name or "qwen2_5" in model_name:
        text_label = "Qwen2.5-VL"
    else:
        text_label = "Qwen-VL"
    polish_tokens = int(vlm_cfg.get("max_new_tokens", 2048))
    route_tokens = int(vlm_cfg.get("max_new_tokens_route", min(1024, polish_tokens)))

    # Trunk default (2026-07-24): MinerU + Qwen + Qwen when engines.* omitted.
    layout_name = str(engines_cfg.get("layout", "mineru")).lower()
    text_name = str(engines_cfg.get("text", "vlm")).lower()
    formula_name = str(engines_cfg.get("formula", "vlm")).lower()
    if layout_name not in {"surya", "doclayout_yolo", "mineru"}:
        raise EngineError(f"Unknown layout engine: {layout_name}")
    if text_name not in {"vlm", "ppocr", "paddleocr_vl"}:
        raise EngineError(f"Unknown text engine: {text_name}")
    if formula_name not in {"vlm", "got", "unimernet"}:
        raise EngineError(f"Unknown formula engine: {formula_name}")

    layout = LayoutAnalyzer(
        dpi=int(layout_cfg.get("dpi", 200)),
        device=str(layout_cfg.get("device", "cuda")),
        force_backend=str(layout_cfg.get("force_backend", "")),
    )
    formula_engine = (
        GotFormulaEngine()
        if formula_name == "got"
        else UnimernetFormulaEngine(device=str(layout_cfg.get("device", "cuda")))
        if formula_name == "unimernet"
        else VlmFormulaEngine(vlm, max_new_tokens=route_tokens)
    )
    math = MathRouter(formula_engine=formula_engine, max_new_tokens=route_tokens)
    if text_name == "ppocr":
        text_engine = PpocrTextEngine()
        table_engine = PpocrTextEngine()
    elif text_name == "paddleocr_vl":
        device = str(layout_cfg.get("device", "gpu"))
        text_engine = PaddleOcrVlTextEngine(device=device)
        table_engine = PaddleOcrVlTextEngine(device=device)
    else:
        text_engine = VlmTextEngine(vlm, max_new_tokens=route_tokens)
        table_engine = VlmTextEngine(vlm, max_new_tokens=route_tokens, prompt=TABLE_ROUTER_PROMPT)
    text = TextRouter(
        model_name=text_label,
        text_engine=text_engine,
        table_engine=table_engine,
        max_new_tokens=route_tokens,
        structured_ocr_client=build_mcq_structured_client(
            cfg.get("structured_ocr") or {},
            default_model_name=str(
                vlm_cfg.get("model_name", "Qwen/Qwen3-VL-8B-Instruct")
            ),
        ),
        structured_ocr_shadow_mode=bool(
            (cfg.get("structured_ocr") or {}).get("shadow_mode", True)
        ),
        local_mcq_validation_enabled=bool(
            (cfg.get("local_mcq_validation") or {}).get("enabled", True)
        ),
    )
    crop_dir = Path(paths.get("crop_dir", "3.分析結果/output/crops"))
    pipe_cfg = cfg.get("pipeline") or {}
    skip_figures = bool(pipe_cfg.get("skip_figures", True))
    extract_figures = bool(pipe_cfg.get("extract_figures", True))
    nup_cfg = cfg.get("nup") or {}
    nup_enabled = bool(nup_cfg.get("enabled", True))
    nup_confidence_threshold = float(nup_cfg.get("confidence_threshold", 0.75))
    nup_margin_norm = float(nup_cfg.get("margin_norm", 0.01))
    router = DynamicRouter(math, text, crop_dir=crop_dir, skip_figures=skip_figures)
    mcq_stage3 = str(pipe_cfg.get("mcq_stage3", _MCQ_STAGE3_DEFAULT)).strip().lower()
    if mcq_stage3 not in {"sanitize", "paddle_sanitize", "vlm"}:
        mcq_stage3 = _MCQ_STAGE3_DEFAULT
    if text_name == "paddleocr_vl" and mcq_stage3 == "sanitize":
        mcq_stage3 = "paddle_sanitize"

    base_layout_engine = (
        DocLayoutYoloEngine(device=str(layout_cfg.get("device", "cuda")))
        if layout_name == "doclayout_yolo"
        else MineruLayoutEngine(device=str(layout_cfg.get("device", "cuda")))
        if layout_name == "mineru"
        else SuryaLayoutEngine(layout)
    )
    layout_engine = (
        DseMcqLayoutEngine(
            profile=load_mcq_profile(default_math_cp_p2_path()),
            fallback_engine=base_layout_engine,
        )
        if dse_mcq
        else base_layout_engine
    )

    return PipelineManager(
        layout=layout,
        layout_engine=layout_engine,
        router=router,
        assembler=DraftAssembler(),
        polisher=FinalPolisher(vlm, mcq_stage3=mcq_stage3),
        output_dir=Path(paths.get("output_dir", "3.分析結果/output")),
        pages_dir=Path(paths.get("pages_dir", "1_收集資料/data/pdf_pages")),
        extract_figures=extract_figures,
        nup_enabled=nup_enabled,
        nup_confidence_threshold=nup_confidence_threshold,
        nup_margin_norm=nup_margin_norm,
    )
