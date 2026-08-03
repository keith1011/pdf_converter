"""Gated two-column reading order."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.reading_order import assign_reading_order, detect_two_column


def _block(
    bid: str,
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    order: int = 0,
) -> LayoutBlock:
    return LayoutBlock(
        block_id=bid,
        block_type=BlockType.TEXT,
        bbox=BBox(x1, y1, x2, y2),
        order=order,
        page=1,
        image_path=Path("page.png"),
    )


def test_single_column_stays_row_major():
    # Full-width-ish stack — no clear dual columns.
    blocks = [
        _block("a", x1=10, y1=200, x2=400, y2=240, order=0),
        _block("b", x1=10, y1=20, x2=400, y2=60, order=1),
        _block("c", x1=10, y1=100, x2=400, y2=140, order=2),
    ]
    assert detect_two_column(blocks) is False
    ordered = assign_reading_order(blocks)
    assert [b.block_id for b in ordered] == ["b", "c", "a"]
    assert all(b.meta.get("reading_order") == "row_major" for b in ordered)


def test_two_column_uses_column_major_not_ltr_zigzag():
    # Left: L0 (y=10), L1 (y=100). Right: R0 (y=15), R1 (y=105).
    # Row-major zigzag would be L0, R0, L1, R1.
    # Column-major should be L0, L1, R0, R1.
    blocks = [
        _block("R0", x1=220, y1=15, x2=400, y2=40, order=0),
        _block("L1", x1=10, y1=100, x2=180, y2=130, order=1),
        _block("R1", x1=220, y1=105, x2=400, y2=135, order=2),
        _block("L0", x1=10, y1=10, x2=180, y2=40, order=3),
        _block("L2", x1=10, y1=200, x2=180, y2=230, order=4),
        _block("R2", x1=220, y1=205, x2=400, y2=235, order=5),
        _block("L3", x1=10, y1=300, x2=180, y2=330, order=6),
        _block("R3", x1=220, y1=305, x2=400, y2=335, order=7),
    ]
    assert detect_two_column(blocks) is True
    ordered = assign_reading_order(list(blocks))
    assert [b.block_id for b in ordered] == [
        "L0",
        "L1",
        "L2",
        "L3",
        "R0",
        "R1",
        "R2",
        "R3",
    ]
    assert all(b.meta.get("reading_order") == "column_major" for b in ordered)
    assert [b.order for b in ordered] == list(range(8))


def test_sparse_page_not_treated_as_two_column():
    blocks = [
        _block("only_l", x1=10, y1=10, x2=100, y2=40),
        _block("only_r", x1=300, y1=12, x2=400, y2=40),
    ]
    assert detect_two_column(blocks) is False
