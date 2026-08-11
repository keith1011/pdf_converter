from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from .classification_models import (
    ClassifiedFigureAsset,
    FigureClassification,
    ReviewedClassification,
)
from .models import resolve_bundle_path
from .proposal import sha256_file


def _load_pending_asset(source_dir: Path) -> ClassifiedFigureAsset:
    asset_path = source_dir / "figure_asset.json"
    asset = ClassifiedFigureAsset.model_validate_json(asset_path.read_text(encoding="utf-8"))
    status = asset.classification.status
    if status not in {"pending", "failed"}:
        raise ValueError("classification review requires a pending or failed B2 asset")
    if status == "pending" and asset.classification.proposed is None:
        raise ValueError("classification review requires a pending proposal")

    crop_path = resolve_bundle_path(source_dir, asset.source.crop_path)
    if not crop_path.is_file():
        raise FileNotFoundError(crop_path)
    if sha256_file(crop_path) != asset.source.sha256:
        raise ValueError("source figure crop hash mismatch")

    classification = asset.classification
    if classification.status == "failed":
        response_reference = classification.response_path
        response_sha256 = classification.response_sha256
        if response_reference is None or response_sha256 is None:
            raise ValueError("failed classification requires a raw response reference")
        response_path = resolve_bundle_path(source_dir, response_reference)
        if not response_path.is_file():
            raise FileNotFoundError(response_path)
        if sha256_file(response_path) != response_sha256:
            raise ValueError("classification response hash mismatch")
    return asset


def _expected_proposal_id(asset: ClassifiedFigureAsset) -> str:
    proposal = asset.classification.proposed
    prompt_version = (
        proposal.prompt_version
        if proposal is not None
        else asset.classification.prompt_version
    )
    if prompt_version is None:
        raise ValueError("classification review requires a proposal prompt version")
    return f"{asset.asset_id}:{prompt_version}"


def _validate_decision_binding(
    asset: ClassifiedFigureAsset,
    decision: ReviewedClassification,
) -> None:
    if decision.source_proposal_id != _expected_proposal_id(asset):
        raise ValueError("review decision does not match the source proposal")
    if decision.status != "approved":
        return

    proposal = asset.classification.proposed
    if proposal is None:
        raise ValueError("approved review requires a proposal")
    if (
        decision.visual_family != proposal.visual_family
        or decision.subtype != proposal.subtype
        or set(decision.secondary_tags) != set(proposal.secondary_tags)
    ):
        raise ValueError("approved decision must match the original proposal")


def _reviewed_asset(
    asset: ClassifiedFigureAsset,
    decision: ReviewedClassification,
) -> ClassifiedFigureAsset:
    classification_payload = asset.classification.model_dump(mode="json")
    classification_payload.update(
        {
            "reviewed": decision.model_dump(mode="json"),
            "status": decision.status,
        }
    )
    classification = FigureClassification.model_validate(classification_payload)
    figure_type = (
        decision.visual_family if decision.status in {"approved", "corrected"} else "unknown"
    )
    payload = asset.model_dump(mode="json")
    payload.update(
        {
            "figure_type": figure_type,
            "classification": classification.model_dump(mode="json"),
        }
    )
    return ClassifiedFigureAsset.model_validate(payload)


def _write_asset(path: Path, asset: ClassifiedFigureAsset) -> None:
    payload = json.dumps(
        asset.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    path.write_bytes((payload + chr(10)).encode("utf-8"))


def review_bundle(
    source_dir: Path,
    destination: Path,
    decision: ReviewedClassification,
) -> ClassifiedFigureAsset:
    if destination.exists():
        raise FileExistsError(destination)

    asset = _load_pending_asset(source_dir)
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
        round_trip = ClassifiedFigureAsset.model_validate_json(
            json_path.read_text(encoding="utf-8")
        )
        if destination.exists():
            raise FileExistsError(destination)
        stage.rename(destination)
        return round_trip
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
