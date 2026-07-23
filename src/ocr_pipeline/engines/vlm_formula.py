from __future__ import annotations

from pathlib import Path

from ocr_pipeline.prompts import MATH_ROUTER_PROMPT
from ocr_pipeline.routers import normalize_display_math


class VlmFormulaEngine:
    def __init__(self, vlm, *, max_new_tokens: int | None = None) -> None:
        self.vlm = vlm
        self.max_new_tokens = max_new_tokens

    def ocr(self, crop_path: Path) -> str:
        raw = self.vlm.generate(
            MATH_ROUTER_PROMPT, image_path=crop_path, max_new_tokens=self.max_new_tokens
        )
        return normalize_display_math(raw)
