"""Crop page images to the DSE content box (drop side margins / footer chrome)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class CropMargins:
    """Relative margins used when contour detection fails (DSE A4 defaults)."""

    left: float = 0.08
    right: float = 0.08
    top: float = 0.05
    bottom: float = 0.08


def _clamp_box(
    x0: int, y0: int, x1: int, y1: int, width: int, height: int
) -> tuple[int, int, int, int]:
    x0 = max(0, min(x0, width - 2))
    y0 = max(0, min(y0, height - 2))
    x1 = max(x0 + 1, min(x1, width))
    y1 = max(y0 + 1, min(y1, height))
    return x0, y0, x1, y1


def margins_box(width: int, height: int, margins: CropMargins) -> tuple[int, int, int, int]:
    x0 = int(width * margins.left)
    y0 = int(height * margins.top)
    x1 = int(width * (1.0 - margins.right))
    y1 = int(height * (1.0 - margins.bottom))
    return _clamp_box(x0, y0, x1, y1, width, height)


def detect_content_box(
    image_bgr: np.ndarray,
    *,
    margins: CropMargins | None = None,
    min_area_ratio: float = 0.25,
) -> tuple[int, int, int, int]:
    """
    Return (x0, y0, x1, y1) for the largest near-rectangular contour.

    Falls back to ``margins`` when no suitable contour is found.
    """
    margins = margins or CropMargins()
    height, width = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    page_area = float(width * height)
    best: tuple[int, int, int, int] | None = None
    best_area = 0.0
    for contour in contours:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) < 4:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        area = float(w * h)
        if area < min_area_ratio * page_area:
            continue
        # Prefer boxes that are not the full page border
        if w >= 0.98 * width and h >= 0.98 * height:
            continue
        if area > best_area:
            best_area = area
            best = (x, y, x + w, y + h)

    if best is None:
        return margins_box(width, height, margins)
    return _clamp_box(*best, width, height)


def crop_content_image(
    image_path: Path,
    *,
    out_path: Path | None = None,
    margins: CropMargins | None = None,
) -> Path:
    """
    Crop ``image_path`` to the content ROI and write ``*.content.png`` (or ``out_path``).

    Returns the written path.
    """
    image_path = Path(image_path)
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"could not read image: {image_path}")
    x0, y0, x1, y1 = detect_content_box(image, margins=margins)
    cropped = image[y0:y1, x0:x1]
    dest = out_path or image_path.with_name(f"{image_path.stem}.content{image_path.suffix}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(dest), cropped):
        raise RuntimeError(f"failed to write crop: {dest}")
    return dest


def crop_page_images(
    page_paths: list[Path],
    *,
    margins: CropMargins | None = None,
) -> list[Path]:
    """Crop each page PNG; return list of ``*.content.png`` paths in order."""
    return [crop_content_image(p, margins=margins) for p in page_paths]
