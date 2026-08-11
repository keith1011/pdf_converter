"""GOT-OCR 2.0 formula adapter with no VLM fallback.

Uses the Hugging Face native checkpoint ``stepfun-ai/GOT-OCR-2.0-hf``
(``GotOcr2ForConditionalGeneration``). The older remote-code repo
``stepfun-ai/GOT-OCR2_0`` requires optional packages such as ``verovio`` and
is not used by default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch

from .base import EngineError

DEFAULT_MODEL_ID = "stepfun-ai/GOT-OCR-2.0-hf"


def _load_got_model(*, model_id: str) -> tuple[Any, Any]:
    """Load GOT-OCR only when a formula crop is first requested."""
    try:
        from transformers import AutoModelForImageTextToText, AutoProcessor
    except ImportError as exc:
        raise EngineError(
            "GOT-OCR requires transformers. Install it with "
            "`uv sync --group got`."
        ) from exc
    try:
        processor = AutoProcessor.from_pretrained(model_id, use_fast=True)
        model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype=torch.bfloat16,
        ).eval()
    except Exception as exc:
        raise EngineError(
            f"GOT-OCR could not load weights {model_id!r}. "
            "Ensure the model is available locally or Hugging Face access works."
        ) from exc
    return model, processor


class GotFormulaEngine:
    """Transcribe a formula crop using GOT-OCR 2.0 (HF generate path)."""

    def __init__(self, *, model_id: str = DEFAULT_MODEL_ID) -> None:
        self.model_id = model_id
        self._model: Any | None = None
        self._processor: Any | None = None

    def _ensure_model(self) -> tuple[Any, Any]:
        if self._model is None or self._processor is None:
            self._model, self._processor = _load_got_model(model_id=self.model_id)
        return self._model, self._processor

    def ocr(self, crop_path: Path) -> str:
        model, processor = self._ensure_model()
        try:
            inputs = processor(
                str(crop_path),
                return_tensors="pt",
                format=True,
            ).to(model.device)
            generate_ids = model.generate(
                **inputs,
                do_sample=False,
                tokenizer=processor.tokenizer,
                stop_strings="<|im_end|>",
                max_new_tokens=1024,
            )
            prompt_len = int(inputs["input_ids"].shape[1])
            text = processor.decode(
                generate_ids[0, prompt_len:],
                skip_special_tokens=True,
            )
        except Exception as exc:
            raise EngineError(f"GOT-OCR inference failed for {crop_path}.") from exc
        return str(text).strip()
