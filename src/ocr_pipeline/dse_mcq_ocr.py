"""Load saved light-OCR lines for DSE MCQ region cutting."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .dse_mcq_types import OcrLine


def read_rapidocr_lines(image_path: Path) -> list[OcrLine]:
    """Read lightweight OCR anchors for one DSE page."""
    from rapidocr_onnxruntime import RapidOCR

    result, _elapse = RapidOCR()(str(image_path))
    with Image.open(image_path) as image:
        width, height = image.size
    lines: list[OcrLine] = []
    for item in result or []:
        box, text, _score = item[0], item[1], item[2]
        xs = [point[0] for point in box]
        ys = [point[1] for point in box]
        lines.append(
            OcrLine(
                text=str(text),
                bbox=(float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))),
                page_width=float(width),
                page_height=float(height),
            )
        )
    return sorted(lines, key=lambda line: (line.bbox[1], line.bbox[0]))


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
