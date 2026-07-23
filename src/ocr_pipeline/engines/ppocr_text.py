"""PP-OCR text adapter.

Traditional Chinese uses PaddleOCR's documented ``chinese_cht`` language code.
The adapter prefers PaddleOCR 3.x ``predict()`` (``rec_texts``), with a legacy
``.ocr()`` fallback for older result shapes. It intentionally has no VLM
fallback: unavailable OCR dependencies must fail loudly so experiment results
remain attributable to PP-OCR.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import EngineError

TRADITIONAL_CHINESE_LANG = "chinese_cht"


def _load_paddle_ocr(*, lang: str) -> Any:
    """Load PaddleOCR only when the engine first processes a crop."""
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise EngineError(
            "PP-OCR requires paddleocr. Install it with `pip install -r requirements-ppocr.txt`."
        ) from exc
    # Orientation/unwarp models add startup cost and are unnecessary for crops.
    return PaddleOCR(
        lang=lang,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
    )


def _extract_lines(result: Any) -> list[str]:
    """Extract recognized strings from PaddleOCR 3.x or legacy results."""
    lines: list[str] = []

    def visit(value: Any) -> None:
        if value is None:
            return
        if hasattr(value, "get") and not isinstance(value, (str, bytes)):
            texts = value.get("rec_texts")
            if isinstance(texts, list):
                lines.extend(str(t) for t in texts if t)
                return
        if isinstance(value, tuple) and len(value) >= 2 and isinstance(value[0], str):
            lines.append(value[0])
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(result)
    return lines


def _run_paddle_ocr(client: Any, crop_path: Path) -> Any:
    """Call predict() on 3.x; fall back to ocr() without deprecated cls=."""
    if hasattr(client, "predict"):
        return client.predict(str(crop_path))
    return client.ocr(str(crop_path))


class PpocrTextEngine:
    """Read crop text with PP-OCR, keeping the PaddleOCR model lazy."""

    def __init__(self, *, lang: str = TRADITIONAL_CHINESE_LANG) -> None:
        self.lang = lang
        self._ocr: Any | None = None

    def ocr(self, crop_path: Path) -> str:
        if self._ocr is None:
            self._ocr = _load_paddle_ocr(lang=self.lang)
        try:
            result = _run_paddle_ocr(self._ocr, crop_path)
        except Exception as exc:
            raise EngineError(f"PP-OCR inference failed for {crop_path}.") from exc
        return "\n".join(_extract_lines(result)).strip()
