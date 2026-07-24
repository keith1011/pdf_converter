"""Deprecated local GLM-4.6V-Flash client (optional VlmClient backend).

Kept for experiments and backwards compatibility; prefer the Qwen backend.
"""

from __future__ import annotations

from pathlib import Path

import torch

from .vlm_client import run_vlm_generate


class Glm46VFlashClient:
    """Thin wrapper around local zai-org/GLM-4.6V-Flash."""

    def __init__(
        self,
        model_name: str = "zai-org/GLM-4.6V-Flash",
        *,
        load_in_4bit: bool = True,
        max_new_tokens: int = 2048,
        temperature: float = 0.0,
        max_pixels: int = 1003520,
    ):
        self.model_name = model_name
        self.load_in_4bit = load_in_4bit
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.max_pixels = max_pixels
        self.model = None
        self.processor = None

    def load(self) -> None:
        if self.model is not None:
            return
        from transformers import AutoProcessor, BitsAndBytesConfig

        print(f"[GLM] Loading {self.model_name} (4bit={self.load_in_4bit})")
        self.processor = AutoProcessor.from_pretrained(self.model_name, trust_remote_code=True)

        model_kwargs: dict = {"device_map": "auto", "trust_remote_code": True}
        if self.load_in_4bit:
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
        else:
            model_kwargs["torch_dtype"] = torch.bfloat16

        try:
            from transformers import Glm4vForConditionalGeneration

            self.model = Glm4vForConditionalGeneration.from_pretrained(
                self.model_name, **model_kwargs
            )
        except Exception:
            from transformers import AutoModelForImageTextToText

            self.model = AutoModelForImageTextToText.from_pretrained(
                self.model_name, **model_kwargs
            )
        self.model.eval()

    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        self.load()
        assert self.model is not None and self.processor is not None
        token_budget = self.max_new_tokens if max_new_tokens is None else int(max_new_tokens)
        return run_vlm_generate(
            model=self.model,
            processor=self.processor,
            prompt=prompt,
            image_path=image_path,
            max_pixels=self.max_pixels,
            max_new_tokens=token_budget,
            temperature=self.temperature,
        )
