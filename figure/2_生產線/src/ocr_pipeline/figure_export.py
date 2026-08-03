from __future__ import annotations

from pathlib import Path

from .models import (
    BlockType,
    ContentSegment,
    IntegrityStatus,
    LayoutBlock,
    SegmentKind,
)
from .prompts import FIGURE_CAPTION_PROMPT


def _ensure_crop(block: LayoutBlock, figures_dir: Path) -> Path:
    figures_dir.mkdir(parents=True, exist_ok=True)
    dest = figures_dir / f"{block.block_id}.png"
    if block.crop_path is not None and block.crop_path.is_file():
        dest.write_bytes(block.crop_path.read_bytes())
        return dest
    from PIL import Image

    with Image.open(block.image_path) as im:
        image = im.convert("RGB")
        image.load()
        w, h = image.size
        box = block.bbox.clamp(w, h).as_int_tuple()
        crop = image.crop(box)
    crop.save(dest)
    return dest


def export_figures(
    *,
    blocks: list[LayoutBlock],
    figures_dir: Path,
    vlm,
    max_new_tokens: int = 128,
) -> tuple[list[ContentSegment], list[str]]:
    segments: list[ContentSegment] = []
    warnings: list[str] = []
    for block in blocks:
        if block.block_type is not BlockType.FIGURE:
            continue
        try:
            crop_path = _ensure_crop(block, figures_dir)
            caption = vlm.generate(
                FIGURE_CAPTION_PROMPT,
                image_path=crop_path,
                max_new_tokens=max_new_tokens,
            ).strip()
            if not caption:
                raise RuntimeError("empty caption")
            segments.append(
                ContentSegment(
                    kind=SegmentKind.FIGURE,
                    text=caption,
                    source_block_id=block.block_id,
                    bbox=block.bbox,
                    integrity=IntegrityStatus.OK,
                    crop_relpath=f"figures/{block.block_id}.png",
                )
            )
        except Exception as exc:  # noqa: BLE001 — per-figure isolation
            warnings.append(f"figure {block.block_id}: {exc}")
    return segments, warnings
