"""Load saved light-OCR lines for DSE MCQ region cutting."""

from __future__ import annotations

import json
from pathlib import Path

from .dse_mcq_types import OcrLine


def load_ocr_lines_json(path: Path) -> list[OcrLine]:
    """Load precomputed lines JSON (unit-test / B-side dump friendly)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    page_w = float(data["page_width"])
    page_h = float(data["page_height"])
    lines: list[OcrLine] = []
    for item in data.get("lines") or []:
        bbox = item["bbox"]
        lines.append(
            OcrLine(
                text=str(item.get("text") or ""),
                bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                page_width=page_w,
                page_height=page_h,
            )
        )
    return lines
