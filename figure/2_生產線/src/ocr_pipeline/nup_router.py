"""N-up gate: classify → threshold → fixed crop or whole-page fallback."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from .models import LayoutBlock
from .nup_classify import classify_nup
from .nup_crop import crop_panels, fixed_panel_boxes
from .nup_merge import merge_panel_blocks
from .nup_types import NupClass, NupDecision, NupPanel


def decide_nup(
    image_path: Path,
    page_index: int,
    *,
    threshold: float,
    margin_norm: float,
    page_dir: Path | None,
    enabled: bool = True,
) -> NupDecision:
    if not enabled:
        decision = NupDecision(
            page_index=page_index,
            nup_class=NupClass.ONE,
            confidence=1.0,
            threshold=threshold,
            fallback=True,
            panels=[],
        )
        if page_dir is not None:
            write_nup_json(page_dir / "nup.json", decision)
        return decision

    nup_class, confidence = classify_nup(image_path)
    fallback = (
        nup_class in (NupClass.ONE, NupClass.UNCERTAIN) or confidence < threshold
    )
    panels: list[NupPanel] = []
    if not fallback and nup_class in (NupClass.TWO_LR, NupClass.FOUR_2X2):
        split_x = 0.5
        if nup_class is NupClass.TWO_LR:
            from .nup_classify import find_best_vertical_split

            _, split_x = find_best_vertical_split(image_path)
        boxes = fixed_panel_boxes(
            nup_class, margin_norm=margin_norm, split_x=split_x
        )
        panels = [NupPanel(vid, bbox) for vid, bbox in boxes]
        if page_dir is not None:
            panels = crop_panels(image_path, panels, page_dir / "panels")

    decision = NupDecision(
        page_index=page_index,
        nup_class=nup_class,
        confidence=confidence,
        threshold=threshold,
        fallback=fallback,
        panels=panels,
    )
    if page_dir is not None:
        write_nup_json(page_dir / "nup.json", decision)
    return decision


def analyze_page_with_nup(
    analyze_fn: Callable[[Path, int], list[LayoutBlock]],
    image_path: Path,
    *,
    page: int,
    page_dir: Path,
    enabled: bool,
    threshold: float,
    margin_norm: float,
) -> list[LayoutBlock]:
    """Classify/crop then run layout analyze once (fallback) or per panel."""
    nup_dir = page_dir / "nup" / f"page_{page:03d}"
    nup_dir.mkdir(parents=True, exist_ok=True)
    decision = decide_nup(
        image_path,
        page,
        threshold=threshold,
        margin_norm=margin_norm,
        page_dir=nup_dir,
        enabled=enabled,
    )
    print(
        f"  nup class={decision.nup_class.value} conf={decision.confidence:.3f} "
        f"fallback={decision.fallback} panels={len(decision.panels)}"
    )
    if decision.fallback or not decision.panels:
        blocks = analyze_fn(image_path, page)
        for b in blocks:
            b.meta.setdefault("version_id", "v0")
        return blocks

    panel_pairs: list[tuple[NupPanel, list[LayoutBlock]]] = []
    for panel in decision.panels:
        if panel.path is None:
            continue
        panel_pairs.append((panel, analyze_fn(panel.path, page)))

    with Image.open(image_path) as im:
        page_w, page_h = im.size
    return merge_panel_blocks(
        panel_pairs,
        page=page,
        page_image=image_path,
        page_w=page_w,
        page_h=page_h,
    )


def write_nup_json(path: Path, decision: NupDecision) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "page_index": decision.page_index,
        "class": decision.nup_class.value,
        "confidence": decision.confidence,
        "threshold": decision.threshold,
        "fallback": decision.fallback,
        "panels": [
            {
                "version_id": p.version_id,
                "bbox": list(p.bbox_norm),
                "path": str(p.path) if p.path is not None else None,
                "semantic": p.semantic,
            }
            for p in decision.panels
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_nup_json(path: Path) -> NupDecision:
    data = json.loads(path.read_text(encoding="utf-8"))
    panels = [
        NupPanel(
            version_id=p["version_id"],
            bbox_norm=tuple(p["bbox"]),  # type: ignore[arg-type]
            path=Path(p["path"]) if p.get("path") else None,
            semantic=p.get("semantic"),
        )
        for p in data.get("panels", [])
    ]
    return NupDecision(
        page_index=int(data["page_index"]),
        nup_class=NupClass(data["class"]),
        confidence=float(data["confidence"]),
        threshold=float(data["threshold"]),
        fallback=bool(data["fallback"]),
        panels=panels,
    )
