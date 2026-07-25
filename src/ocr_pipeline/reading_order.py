"""Reading-order helpers: gated two-column (column-major) vs default row-major."""

from __future__ import annotations

from .models import LayoutBlock

# Conservative defaults: avoid flipping normal single-column pages.
_MIN_BLOCKS = 8
_MIN_PER_COLUMN = 3
_MIN_GAP_FRAC = 0.03
# Ignore very wide boxes when measuring the gutter (headers / banners).
_MAX_COL_WIDTH_FRAC = 0.45


def _center_x(block: LayoutBlock) -> float:
    return (block.bbox.x1 + block.bbox.x2) / 2.0


def detect_two_column(
    blocks: list[LayoutBlock],
    *,
    min_blocks: int = _MIN_BLOCKS,
    min_per_column: int = _MIN_PER_COLUMN,
    min_gap_frac: float = _MIN_GAP_FRAC,
    max_col_width_frac: float = _MAX_COL_WIDTH_FRAC,
) -> bool:
    """
    True when blocks form two side-by-side columns with a clear horizontal gap.

    Single-column / sparse pages return False so ``(y1, x1)`` ordering is kept.
    """
    if len(blocks) < min_blocks:
        return False
    x1_min = min(b.bbox.x1 for b in blocks)
    x2_max = max(b.bbox.x2 for b in blocks)
    width = x2_max - x1_min
    if width <= 1.0:
        return False
    mid = x1_min + width / 2.0
    # Prefer narrow boxes for gutter math; wide banners often bleed into the center.
    candidates = [
        b for b in blocks if (b.bbox.x2 - b.bbox.x1) < width * max_col_width_frac
    ]
    if len(candidates) < min_blocks:
        candidates = list(blocks)
    left = [b for b in candidates if _center_x(b) < mid]
    right = [b for b in candidates if _center_x(b) >= mid]
    if len(left) < min_per_column or len(right) < min_per_column:
        return False
    gap = min(b.bbox.x1 for b in right) - max(b.bbox.x2 for b in left)
    if gap < width * min_gap_frac:
        return False
    # Centers of the two columns should be well separated (not a mild indent).
    left_cx = sum(_center_x(b) for b in left) / len(left)
    right_cx = sum(_center_x(b) for b in right) / len(right)
    return (right_cx - left_cx) >= width * 0.25


def assign_reading_order(blocks: list[LayoutBlock]) -> list[LayoutBlock]:
    """
    Assign ``block.order`` for Stage2.

    - Default: row-major ``(y1, x1)`` (unchanged trunk behavior).
    - Two-column pages: column-major — finish left column top→bottom, then right.
    """
    if not blocks:
        return blocks

    if detect_two_column(blocks):
        x1_min = min(b.bbox.x1 for b in blocks)
        x2_max = max(b.bbox.x2 for b in blocks)
        mid = x1_min + (x2_max - x1_min) / 2.0
        left = sorted(
            (b for b in blocks if _center_x(b) < mid),
            key=lambda b: (b.bbox.y1, b.bbox.x1, b.order),
        )
        right = sorted(
            (b for b in blocks if _center_x(b) >= mid),
            key=lambda b: (b.bbox.y1, b.bbox.x1, b.order),
        )
        ordered = [*left, *right]
        mode = "column_major"
    else:
        ordered = sorted(blocks, key=lambda b: (b.bbox.y1, b.bbox.x1, b.order))
        mode = "row_major"

    for order, block in enumerate(ordered):
        block.order = order
        block.meta["reading_order"] = mode
    return ordered
