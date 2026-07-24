"""OCR pipeline package: layout + dynamic routing + VLM arrange."""

from __future__ import annotations

from typing import Any

__all__ = ["PipelineManager", "build_default_pipeline", "load_ocr_config"]


def __getattr__(name: str) -> Any:
    # Lazy exports so lightweight modules (content_first, job_export) import
    # without pulling torch / optional engine stacks.
    if name == "PipelineManager":
        from .pipeline import PipelineManager

        return PipelineManager
    if name == "build_default_pipeline":
        from .factory import build_default_pipeline

        return build_default_pipeline
    if name == "load_ocr_config":
        from .factory import load_ocr_config

        return load_ocr_config
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
