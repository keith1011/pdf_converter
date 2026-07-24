"""Persist / resume Surya LayoutBlock results (Phase 2.5b / 2.8)."""

from __future__ import annotations

import json
from pathlib import Path

from .models import BBox, BlockType, LayoutBlock, PageResult

LAYOUT_ARTIFACT_VERSION = 1
LAYOUT_ARTIFACT_NAME = "layout.json"


def layout_artifact_path(page_dir: Path) -> Path:
    return page_dir / LAYOUT_ARTIFACT_NAME


def _block_to_dict(block: LayoutBlock) -> dict:
    return {
        "block_id": block.block_id,
        "block_type": block.block_type.value,
        "bbox": [block.bbox.x1, block.bbox.y1, block.bbox.x2, block.bbox.y2],
        "order": block.order,
        "page": block.page,
        "image_path": str(block.image_path),
        "crop_path": str(block.crop_path) if block.crop_path else None,
        "raw_text": block.raw_text,
        "latex": block.latex,
        "meta": dict(block.meta or {}),
    }


def _block_from_dict(data: dict) -> LayoutBlock:
    bbox = data["bbox"]
    crop = data.get("crop_path")
    return LayoutBlock(
        block_id=str(data["block_id"]),
        block_type=BlockType(str(data["block_type"])),
        bbox=BBox(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
        order=int(data["order"]),
        page=int(data["page"]),
        image_path=Path(str(data["image_path"])),
        crop_path=Path(crop) if crop else None,
        raw_text=str(data.get("raw_text") or ""),
        latex=str(data.get("latex") or ""),
        meta=dict(data.get("meta") or {}),
    )


def save_layout_artifact(
    path: Path,
    *,
    source: str,
    pdf_path: Path | None,
    pages: list[PageResult],
) -> Path:
    """Write layout-only PageResults (blocks may be empty of OCR text)."""
    payload = {
        "version": LAYOUT_ARTIFACT_VERSION,
        "source": source,
        "pdf": str(pdf_path) if pdf_path else None,
        "pages": [
            {
                "page": pr.page,
                "image_path": str(pr.image_path),
                "blocks": [_block_to_dict(b) for b in pr.blocks],
            }
            for pr in pages
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_layout_artifact(path: Path) -> list[PageResult]:
    """Load PageResults with LayoutBlocks; raises ValueError on bad schema."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if int(data.get("version", 0)) != LAYOUT_ARTIFACT_VERSION:
        raise ValueError(
            f"Unsupported layout artifact version: {data.get('version')} "
            f"(expected {LAYOUT_ARTIFACT_VERSION})"
        )
    pages: list[PageResult] = []
    for page in data.get("pages") or []:
        image_path = Path(str(page["image_path"]))
        blocks = [_block_from_dict(b) for b in (page.get("blocks") or [])]
        for b in blocks:
            b.image_path = image_path
        pages.append(
            PageResult(
                page=int(page["page"]),
                image_path=image_path,
                blocks=blocks,
                draft="",
            )
        )
    if not pages:
        raise ValueError(f"Layout artifact has no pages: {path}")
    return pages
