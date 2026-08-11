from __future__ import annotations

import json
import re
import shutil
import uuid
from collections.abc import Sequence
from pathlib import Path

from ocr_pipeline.models import ContentSegment

from .label_ocr_models import LabeledFigureAsset
from .models import resolve_bundle_path
from .pageir import build_reviewed_figure_segment, load_publishable_asset
from .proposal import sha256_file

_QUESTION_SUFFIX = re.compile(r"-q(?P<question_id>\d{3})$")
_DOCUMENT_ID = re.compile(r"^hk-dse-(?P<year>\d{4})-math-p2$")


def _segment_payload(segment: ContentSegment) -> dict[str, object]:
    return {
        "kind": segment.kind.value,
        "text": segment.text,
        "source_block_id": segment.source_block_id,
        "bbox": [
            segment.bbox.x1,
            segment.bbox.y1,
            segment.bbox.x2,
            segment.bbox.y2,
        ],
        "integrity": segment.integrity.value,
        "crop_relpath": segment.crop_relpath,
        "version_id": segment.version_id,
    }


def _question_anchor(asset: LabeledFigureAsset) -> str:
    match = _QUESTION_SUFFIX.search(asset.parent_question_id)
    if match is None:
        raise ValueError("Figure parent_question_id has no question anchor")
    return f"p{asset.source.page:03d}_q{int(match.group('question_id')):03d}"


def _load_pageir(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("pages"), list):
        raise ValueError("PageIR must contain a pages list")
    return payload


def _validate_document_binding(pageir_path: Path, asset: LabeledFigureAsset) -> None:
    match = _DOCUMENT_ID.fullmatch(asset.document_id)
    if match is None:
        raise ValueError("unsupported Figure document identity")
    suffix = ".pageir.json"
    if not pageir_path.name.endswith(suffix):
        raise ValueError("PageIR filename must end with .pageir.json")
    pageir_document = pageir_path.name[: -len(suffix)]
    expected_document = f"{match.group('year')}p2"
    if pageir_document != expected_document:
        raise ValueError(
            f"PageIR document {pageir_document} does not match {asset.document_id}"
        )


def _anchor_locations(payload: dict[str, object]) -> dict[str, list[tuple[dict, int]]]:
    locations: dict[str, list[tuple[dict, int]]] = {}
    pages = payload["pages"]
    assert isinstance(pages, list)
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("segments"), list):
            raise ValueError("each PageIR page must contain a segments list")
        for index, segment in enumerate(page["segments"]):
            if not isinstance(segment, dict):
                raise ValueError("each PageIR segment must be an object")
            source_block_id = segment.get("source_block_id")
            if isinstance(source_block_id, str):
                locations.setdefault(source_block_id, []).append((page, index))
    return locations


def publish_reviewed_figures(
    *,
    pageir_path: Path,
    bundle_dirs: Sequence[Path],
    destination: Path,
) -> Path:
    if destination.exists():
        raise FileExistsError(destination)
    if not bundle_dirs:
        raise ValueError("at least one reviewed Figure bundle is required")

    payload = _load_pageir(pageir_path)
    assets: list[tuple[Path, LabeledFigureAsset, str, ContentSegment]] = []
    seen_asset_ids: set[str] = set()
    for bundle_dir in bundle_dirs:
        asset = load_publishable_asset(bundle_dir)
        _validate_document_binding(pageir_path, asset)
        if asset.asset_id in seen_asset_ids:
            raise ValueError(f"duplicate asset_id: {asset.asset_id}")
        seen_asset_ids.add(asset.asset_id)
        crop_relpath = f"figures/{asset.asset_id}-{asset.source.sha256[:12]}.png"
        segment = build_reviewed_figure_segment(
            bundle_dir,
            crop_relpath=crop_relpath,
        )
        assets.append((bundle_dir, asset, _question_anchor(asset), segment))

    locations = _anchor_locations(payload)
    by_anchor: dict[str, list[tuple[Path, LabeledFigureAsset, ContentSegment]]] = {}
    for bundle_dir, asset, anchor, segment in assets:
        if locations.get(asset.asset_id):
            raise ValueError(f"PageIR already contains asset_id: {asset.asset_id}")
        matches = locations.get(anchor, [])
        if len(matches) != 1:
            raise ValueError(
                f"question anchor must occur exactly once: {anchor} (got {len(matches)})"
            )
        page, _ = matches[0]
        if page.get("page_index") != asset.source.page:
            raise ValueError(f"question anchor is on the wrong page: {anchor}")
        by_anchor.setdefault(anchor, []).append((bundle_dir, asset, segment))

    pages = payload["pages"]
    assert isinstance(pages, list)
    for page in pages:
        assert isinstance(page, dict)
        original_segments = page["segments"]
        assert isinstance(original_segments, list)
        merged_segments: list[dict[str, object]] = []
        for source_segment in original_segments:
            assert isinstance(source_segment, dict)
            merged_segments.append(source_segment)
            anchor = source_segment.get("source_block_id")
            if not isinstance(anchor, str) or anchor not in by_anchor:
                continue
            reviewed = sorted(by_anchor[anchor], key=lambda item: item[1].asset_id)
            merged_segments.extend(_segment_payload(item[2]) for item in reviewed)
        page["segments"] = merged_segments

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / f".{destination.name}.staging-{uuid.uuid4().hex}"
    stage.mkdir()
    try:
        figures_dir = stage / "figures"
        figures_dir.mkdir()
        for bundle_dir, asset, _, _ in assets:
            source_crop = resolve_bundle_path(bundle_dir, asset.source.crop_path)
            target_crop = figures_dir / f"{asset.asset_id}-{asset.source.sha256[:12]}.png"
            shutil.copy2(source_crop, target_crop)
            if sha256_file(target_crop) != asset.source.sha256:
                raise ValueError("copied figure crop hash mismatch")

        output_path = stage / pageir_path.name
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if destination.exists():
            raise FileExistsError(destination)
        stage.rename(destination)
        return destination / pageir_path.name
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
