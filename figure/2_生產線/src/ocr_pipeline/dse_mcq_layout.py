"""Write MCQ regions as layout.json + crop PNGs for --reuse-layout."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from .dse_mcq_types import McqRegion
from .layout_artifact import layout_artifact_path, save_layout_artifact
from .models import BBox, BlockType, LayoutBlock, PageResult


def select_mcq_page_images(
    images: list[Path], *, skip_first_page: bool = False
) -> list[Path]:
    """Return DSE MCQ page images, optionally excluding the instructions cover."""
    if not skip_first_page:
        return images
    return [image for image in images if image.stem != "page_001"]
logger = logging.getLogger(__name__)


def _crop_box(
    bbox: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    ix1 = max(0, int(x1))
    iy1 = max(0, int(y1))
    ix2 = min(width, max(ix1 + 1, int(x2)))
    iy2 = min(height, max(iy1 + 1, int(y2)))
    return ix1, iy1, ix2, iy2


def regions_to_layout_blocks(
    image_path: Path,
    regions: list[McqRegion],
    *,
    page: int,
    profile_id: str,
    crops_dir: Path,
) -> list[LayoutBlock]:
    """Crop each region and build LayoutBlocks (block_type=text)."""
    crops_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    blocks: list[LayoutBlock] = []
    for order, region in enumerate(regions):
        block_id = f"p{page:03d}_q{region.question_id:03d}"
        box = _crop_box(region.bbox, w, h)
        crop_path = crops_dir / f"{block_id}.png"
        im.crop(box).save(crop_path)
        blocks.append(
            LayoutBlock(
                block_id=block_id,
                block_type=BlockType.TEXT,
                bbox=BBox(float(box[0]), float(box[1]), float(box[2]), float(box[3])),
                order=order,
                page=page,
                image_path=image_path,
                crop_path=crop_path,
                raw_text="",
                latex="",
                meta={
                    "question_id": region.question_id,
                    "profile": profile_id,
                    "anchors": region.anchors.as_dict(),
                    "mcq_incomplete": region.incomplete,
                },
            )
        )
    return blocks


def write_mcq_layout_artifact(
    image_path: Path,
    regions: list[McqRegion],
    *,
    page: int,
    profile_id: str,
    out_dir: Path,
    pdf_path: Path | None = None,
) -> Path | None:
    """
    Persist crops + layout.json under ``out_dir``.

    Returns ``None`` when ``regions`` is empty (caller should fall back to MinerU).
    """
    if not regions:
        logger.warning(
            "dse_mcq_region produced no regions for page %s; MinerU fallback recommended",
            page,
        )
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    crops_dir = out_dir / "crops"
    blocks = regions_to_layout_blocks(
        image_path,
        regions,
        page=page,
        profile_id=profile_id,
        crops_dir=crops_dir,
    )
    page_result = PageResult(page=page, image_path=image_path, blocks=blocks)
    artifact = layout_artifact_path(out_dir)
    save_layout_artifact(
        artifact,
        source=f"dse_mcq_region:{profile_id}",
        pdf_path=pdf_path,
        pages=[page_result],
    )
    return artifact
