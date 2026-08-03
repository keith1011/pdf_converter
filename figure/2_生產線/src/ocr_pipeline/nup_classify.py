"""Projection-based N-up classifier (CPU; no extra VRAM).

Detects 2-up / 4-up via vertical (and horizontal) mid signals:

* **White gutter:** low ink at mid vs content side bands (classic gap).
* **Dark spine:** high ink at mid vs content side bands (booklet crease/shadow).

Booklet scans often have the gutter **off geometric center**. Vertical
search scans candidate cuts in ``[SEARCH_LO, SEARCH_HI]`` and takes the
best score (and that ``split_x`` for cropping).

Side bands use the inner content thirds relative to the candidate cut.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from PIL import Image

from .nup_types import NupClass

_INK_THRESHOLD = 200  # grayscale below this counts as ink
_MID_FRAC = 0.04  # mid window as fraction of axis around candidate
_BAND_INNER = 0.08  # start content band this far from candidate
_BAND_OUTER = 0.35  # end content band this far from candidate (clamped)
_SEARCH_LO = 0.38
_SEARCH_HI = 0.62
_SEARCH_STEP = 0.01
_STRONG = 0.55
_WEAK = 0.30


class ClassifyResult(NamedTuple):
    nup_class: NupClass
    confidence: float
    split_x: float | None = None


def classify_nup(image_path: Path) -> tuple[NupClass, float]:
    """Return (class, confidence). Split position via ``find_best_vertical_split``."""
    result = classify_nup_full(image_path)
    return result.nup_class, result.confidence


def classify_nup_full(image_path: Path) -> ClassifyResult:
    im = Image.open(image_path).convert("L")
    w, h = im.size
    v_proj, h_proj = _projections(im)

    v_score, split_x = _best_split_on_proj(v_proj)
    h_score, _ = _best_split_on_proj(h_proj)
    landscape = (w / max(h, 1)) > 1.25

    if v_score >= _STRONG and h_score >= _STRONG and not landscape:
        return ClassifyResult(NupClass.FOUR_2X2, min(v_score, h_score), split_x)
    if v_score >= _STRONG:
        return ClassifyResult(NupClass.TWO_LR, v_score, split_x)
    if h_score >= _STRONG and not landscape:
        return ClassifyResult(NupClass.UNCERTAIN, h_score, None)
    if max(v_score, h_score) < _WEAK:
        return ClassifyResult(NupClass.ONE, 1.0 - max(v_score, h_score), None)
    return ClassifyResult(NupClass.UNCERTAIN, max(v_score, h_score), None)


def find_best_vertical_split(image_path: Path) -> tuple[float, float]:
    """Return (best_score, split_x_norm) for vertical booklet gutter."""
    im = Image.open(image_path).convert("L")
    v_proj, _ = _projections(im)
    return _best_split_on_proj(v_proj)


def _projections(im: Image.Image) -> tuple[list[float], list[float]]:
    w, h = im.size
    pixels = im.tobytes()
    ink = [1.0 if p < _INK_THRESHOLD else 0.0 for p in pixels]
    v_proj = [0.0] * w
    h_proj = [0.0] * h
    for y in range(h):
        row = y * w
        for x in range(w):
            v = ink[row + x]
            v_proj[x] += v
            h_proj[y] += v
    return [c / h for c in v_proj], [c / w for c in h_proj]


def _best_split_on_proj(proj: list[float]) -> tuple[float, float]:
    n = len(proj)
    if n < 16:
        return 0.0, 0.5
    best_score = 0.0
    best_x = 0.5
    x = _SEARCH_LO
    while x <= _SEARCH_HI + 1e-9:
        score = _split_score_at(proj, x)
        if score > best_score:
            best_score = score
            best_x = x
        x += _SEARCH_STEP
    return best_score, best_x


def _split_score_at(proj: list[float], split_frac: float) -> float:
    n = len(proj)
    mid = int(round(split_frac * (n - 1)))
    half_win = max(1, int(n * _MID_FRAC / 2))
    mid_lo = max(0, mid - half_win)
    mid_hi = min(n, mid + half_win)
    mid_band = proj[mid_lo:mid_hi]
    if not mid_band:
        return 0.0
    mid_mean = sum(mid_band) / len(mid_band)

    left = _band_mean(
        proj,
        int(n * max(0.0, split_frac - _BAND_OUTER)),
        int(n * max(0.0, split_frac - _BAND_INNER)),
    )
    right = _band_mean(
        proj,
        int(n * min(1.0, split_frac + _BAND_INNER)),
        int(n * min(1.0, split_frac + _BAND_OUTER)),
    )
    if left is None or right is None:
        return 0.0
    if left < 0.008 or right < 0.008:
        return 0.0
    flank_mean = (left + right) / 2.0
    if flank_mean <= 1e-6:
        return 0.0

    valley = 0.0
    if mid_mean < flank_mean:
        valley = (flank_mean - mid_mean) / flank_mean
    spine = 0.0
    if mid_mean > flank_mean:
        spine = (mid_mean - flank_mean) / flank_mean
    return max(0.0, min(1.0, max(valley, spine)))


def _band_mean(proj: list[float], lo: int, hi: int) -> float | None:
    lo = max(0, lo)
    hi = min(len(proj), max(lo + 1, hi))
    band = proj[lo:hi]
    if not band:
        return None
    return sum(band) / len(band)
