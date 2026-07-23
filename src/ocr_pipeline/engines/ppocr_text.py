"""PP-OCR text adapter.

Traditional Chinese uses PaddleOCR's documented ``chinese_cht`` language code.
The adapter uses PaddleOCR's established ``PaddleOCR(...).ocr(path, cls=True)``
interface and intentionally has no VLM fallback: unavailable OCR dependencies
must fail loudly so experiment results remain attributable to PP-OCR.
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
            "PP-OCR requires paddleocr. Install it with "
            "`pip install -r requirements-ppocr.txt`."
        ) from exc
    return PaddleOCR(lang=lang)


def _extract_lines(result: Any) -> list[str]:
    """Extract recognized strings from PaddleOCR's nested legacy result."""
    lines: list[str] = []

    def visit(value: Any) -> None:
        if (
            isinstance(value, tuple)
            and len(value) >= 2
            and isinstance(value[0], str)
        ):
            lines.append(value[0])
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(result)
    return lines


class PpocrTextEngine:
    """Read crop text with PP-OCR, keeping the PaddleOCR model lazy."""

    def __init__(self, *, lang: str = TRADITIONAL_CHINESE_LANG) -> None:
        self.lang = lang
        self._ocr: Any | None = None

    def ocr(self, crop_path: Path) -> str:
        if self._ocr is None:
            self._ocr = _load_paddle_ocr(lang=self.lang)
        return "\n".join(_extract_lines(self._ocr.ocr(str(crop_path), cls=True))).strip()
