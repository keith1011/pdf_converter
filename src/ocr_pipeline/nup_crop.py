"""Fixed midline / 2×2 panel crops for N-up pages."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .nup_types import NupClass, NupPanel


def fixed_panel_boxes(
    nup_class: NupClass,
    *,
    margin_norm: float = 0.0,
    split_x: float = 0.5,
) -> list[tuple[str, tuple[float, float, float, float]]]:
    m = max(0.0, min(margin_norm, 0.05))
    if nup_class is NupClass.TWO_LR:
        sx = min(0.75, max(0.25, split_x))
        return [
            ("v0", (0.0 + m, 0.0, sx - m, 1.0)),
            ("v1", (sx + m, 0.0, 1.0 - m, 1.0)),
        ]
    if nup_class is NupClass.FOUR_2X2:
        return [
            ("v0", (0.0 + m, 0.0 + m, 0.5 - m, 0.5 - m)),
            ("v1", (0.5 + m, 0.0 + m, 1.0 - m, 0.5 - m)),
            ("v2", (0.0 + m, 0.5 + m, 0.5 - m, 1.0 - m)),
            ("v3", (0.5 + m, 0.5 + m, 1.0 - m, 1.0 - m)),
        ]
    raise ValueError(f"No fixed boxes for {nup_class}")


def _norm_to_px(
    bbox: tuple[float, float, float, float], w: int, h: int
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return (
        max(0, int(x1 * w)),
        max(0, int(y1 * h)),
        min(w, max(1, int(x2 * w))),
        min(h, max(1, int(y2 * h))),
    )


def crop_panels(image_path: Path, panels: list[NupPanel], out_dir: Path) -> list[NupPanel]:
    out_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    result: list[NupPanel] = []
    for p in panels:
        box = _norm_to_px(p.bbox_norm, w, h)
        crop = im.crop(box)
        path = out_dir / f"{p.version_id}.png"
        crop.save(path)
        result.append(NupPanel(p.version_id, p.bbox_norm, path=path, semantic=p.semantic))
    return result
