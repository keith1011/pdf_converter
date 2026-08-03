"""Remap panel-local layout blocks onto page coordinates; order by version_id."""

from __future__ import annotations

from pathlib import Path

from .models import BBox, LayoutBlock
from .nup_types import NupPanel


def remap_block_to_page(
    block: LayoutBlock,
    panel: NupPanel,
    page_w: int,
    page_h: int,
    *,
    page_image: Path,
) -> LayoutBlock:
    x1n, y1n, _, _ = panel.bbox_norm
    ox = x1n * page_w
    oy = y1n * page_h
    meta = dict(block.meta)
    meta["version_id"] = panel.version_id
    if panel.path is not None:
        meta["panel_image"] = str(panel.path)
    return LayoutBlock(
        block_id=block.block_id,
        block_type=block.block_type,
        bbox=BBox(
            block.bbox.x1 + ox,
            block.bbox.y1 + oy,
            block.bbox.x2 + ox,
            block.bbox.y2 + oy,
        ),
        order=block.order,
        page=block.page,
        image_path=page_image,
        crop_path=block.crop_path,
        raw_text=block.raw_text,
        latex=block.latex,
        meta=meta,
    )


def merge_panel_blocks(
    panel_blocks: list[tuple[NupPanel, list[LayoutBlock]]],
    *,
    page: int,
    page_image: Path,
    page_w: int,
    page_h: int,
) -> list[LayoutBlock]:
    ordered = sorted(panel_blocks, key=lambda pair: pair[0].version_id)
    merged: list[LayoutBlock] = []
    order = 0
    for panel, blocks in ordered:
        for i, block in enumerate(blocks):
            remapped = remap_block_to_page(
                block, panel, page_w, page_h, page_image=page_image
            )
            remapped.page = page
            remapped.order = order
            remapped.block_id = f"p{page:03d}_{panel.version_id}_b{i:03d}"
            merged.append(remapped)
            order += 1
    return merged
