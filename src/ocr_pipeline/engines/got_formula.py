"""GOT-OCR 2.0 formula adapter with no VLM fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import EngineError

DEFAULT_MODEL_ID = "stepfun-ai/GOT-OCR2_0"


def _load_got_model(*, model_id: str) -> tuple[Any, Any]:
    """Load GOT-OCR only when a formula crop is first requested."""
    try:
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise EngineError(
            "GOT-OCR requires transformers. Install it with "
            "`pip install -r requirements-got-ppocr.txt`."
        ) from exc
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            model_id,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            device_map="auto",
        ).eval()
    except Exception as exc:
        raise EngineError(
            f"GOT-OCR could not load weights {model_id!r}. "
            "Ensure the model is available locally or Hugging Face access works."
        ) from exc
    return model, tokenizer


class GotFormulaEngine:
    """Transcribe a formula crop using GOT-OCR 2.0's remote-code chat API."""

    def __init__(self, *, model_id: str = DEFAULT_MODEL_ID) -> None:
        self.model_id = model_id
        self._model: Any | None = None
        self._tokenizer: Any | None = None

    def _ensure_model(self) -> tuple[Any, Any]:
        if self._model is None or self._tokenizer is None:
            self._model, self._tokenizer = _load_got_model(model_id=self.model_id)
        return self._model, self._tokenizer

    def ocr(self, crop_path: Path) -> str:
        model, tokenizer = self._ensure_model()
        try:
            result = model.chat(
                tokenizer,
                image_file=str(crop_path),
                ocr_type="format",
            )
        except Exception as exc:
            raise EngineError(f"GOT-OCR inference failed for {crop_path}.") from exc
        return str(result).strip()
