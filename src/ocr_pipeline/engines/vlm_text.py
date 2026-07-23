from __future__ import annotations

from pathlib import Path

from ocr_pipeline.prompts import TEXT_ROUTER_PROMPT


class VlmTextEngine:
    def __init__(self, vlm, *, max_new_tokens: int | None = None, prompt: str | None = None) -> None:
        self.vlm = vlm
        self.max_new_tokens = max_new_tokens
        self.prompt = prompt or TEXT_ROUTER_PROMPT

    def ocr(self, crop_path: Path) -> str:
        return self.vlm.generate(
            self.prompt, image_path=crop_path, max_new_tokens=self.max_new_tokens
        ).strip()
