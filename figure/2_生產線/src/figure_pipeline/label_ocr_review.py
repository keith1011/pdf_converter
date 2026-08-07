from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from .label_ocr_models import (
    FigureLabelOcr,
    LabeledFigureAsset,
    ReviewedVisibleLabels,
)
from .models import resolve_bundle_path
from .proposal import sha256_file


def _load_reviewable_asset(source_dir: Path) -> LabeledFigureAsset:
    asset_path = source_dir / "figure_asset.json"
    asset = LabeledFigureAsset.model_validate_json(asset_path.read_text(encoding="utf-8"))
    status = asset.label_ocr.status
    if status not in {"pending", "failed"}:
        raise ValueError("label OCR review requires a pending or failed B3 asset")

    crop_path = resolve_bundle_path(source_dir, asset.source.crop_path)
    if not crop_path.is_file():
        raise FileNotFoundError(crop_path)
    if sha256_file(crop_path) != asset.source.sha256:
        raise ValueError("source figure crop hash mismatch")

    if status == "failed":
        response_path = asset.label_ocr.response_path
        response_sha256 = asset.label_ocr.response_sha256
        if response_path is None or response_sha256 is None:
            raise ValueError("failed label OCR requires a raw response reference")
        resolved = resolve_bundle_path(source_dir, response_path)
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        if sha256_file(resolved) != response_sha256:
            raise ValueError("visible label response hash mismatch")
    return asset


def _expected_proposal_id(asset: LabeledFigureAsset) -> str:
    proposal = asset.label_ocr.proposed
    prompt_version = proposal.prompt_version if proposal else asset.label_ocr.prompt_version
    if prompt_version is None:
        raise ValueError("label OCR review requires a prompt version")
    return f"{asset.asset_id}:{prompt_version}"


def _validate_decision_binding(
    asset: LabeledFigureAsset,
    decision: ReviewedVisibleLabels,
) -> None:
    if decision.source_proposal_id != _expected_proposal_id(asset):
        raise ValueError("label review decision does not match the source proposal")
    if decision.status != "approved":
        return
    proposal = asset.label_ocr.proposed
    if proposal is None:
        raise ValueError("approved label review requires a proposal")
    if decision.labels != proposal.labels:
        raise ValueError("approved label review must match the original proposal")


def _reviewed_asset(
    asset: LabeledFigureAsset,
    decision: ReviewedVisibleLabels,
) -> LabeledFigureAsset:
    label_ocr_payload = asset.label_ocr.model_dump(mode="json")
    label_ocr_payload.update(
        {
            "reviewed": decision.model_dump(mode="json"),
            "status": decision.status,
        }
    )
    label_ocr = FigureLabelOcr.model_validate(label_ocr_payload)
    visible_labels = decision.labels if decision.status in {"approved", "corrected"} else []
    payload = asset.model_dump(mode="json")
    payload.update(
        {
            "visible_labels": [label.model_dump(mode="json") for label in visible_labels],
            "label_ocr": label_ocr.model_dump(mode="json"),
        }
    )
    return LabeledFigureAsset.model_validate(payload)


def _write_asset(path: Path, asset: LabeledFigureAsset) -> None:
    payload = json.dumps(
        asset.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    path.write_bytes((payload + chr(10)).encode("utf-8"))


def review_visible_labels_bundle(
    source_dir: Path,
    destination: Path,
    decision: ReviewedVisibleLabels,
) -> LabeledFigureAsset:
    if destination.exists():
        raise FileExistsError(destination)

    asset = _load_reviewable_asset(source_dir)
    _validate_decision_binding(asset, decision)
    reviewed = _reviewed_asset(asset, decision)
    stage = destination.parent / f".{destination.name}.staging-{uuid.uuid4().hex}"

    try:
        shutil.copytree(source_dir, stage, dirs_exist_ok=True)
        json_path = stage / "figure_asset.json"
        _write_asset(json_path, reviewed)

        copied_crop = resolve_bundle_path(stage, reviewed.source.crop_path)
        if sha256_file(copied_crop) != reviewed.source.sha256:
            raise RuntimeError("copied figure crop hash mismatch")
        round_trip = LabeledFigureAsset.model_validate_json(
            json_path.read_text(encoding="utf-8")
        )
        if destination.exists():
            raise FileExistsError(destination)
        stage.rename(destination)
        return round_trip
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
