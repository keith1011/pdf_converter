from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

from ocr_pipeline.models import (
    BBox,
    ContentSegment,
    IntegrityStatus,
    SegmentKind,
)

from .classification_review import _validate_decision_binding as validate_b2_binding
from .label_ocr_models import LabeledFigureAsset
from .label_ocr_review import _validate_decision_binding as validate_b3_binding
from .models import resolve_bundle_path
from .proposal import sha256_file


def _verify_hash(root: Path, relative_path: str, expected: str, label: str) -> None:
    path = resolve_bundle_path(root, relative_path)
    if not path.is_file() or sha256_file(path) != expected:
        raise ValueError(f"{label} hash mismatch")


def _verify_optional_hash(
    root: Path,
    relative_path: str | None,
    expected: str | None,
    label: str,
) -> None:
    if relative_path is None:
        return
    assert expected is not None
    _verify_hash(root, relative_path, expected, label)


def load_publishable_asset(bundle_dir: Path) -> LabeledFigureAsset:
    metadata_path = bundle_dir / "figure_asset.json"
    if not metadata_path.is_file():
        raise ValueError("publishable Figure requires a B3 figure_asset.json")
    asset = LabeledFigureAsset.model_validate_json(
        metadata_path.read_text(encoding="utf-8")
    )
    if asset.classification.status == "rejected" or asset.label_ocr.status == "rejected":
        raise ValueError("rejected Figure is not publishable")
    if asset.classification.status not in {"approved", "corrected"}:
        raise ValueError("B2 classification must be human-reviewed")
    if asset.label_ocr.status not in {"approved", "corrected"}:
        raise ValueError("B3 visible labels must be human-reviewed")
    if asset.classification.reviewed is None or asset.label_ocr.reviewed is None:
        raise ValueError("publishable Figure requires human-reviewed decisions")
    validate_b2_binding(asset, asset.classification.reviewed)
    validate_b3_binding(asset, asset.label_ocr.reviewed)

    _verify_hash(
        bundle_dir,
        asset.source.question_crop_path,
        asset.source.question_crop_sha256,
        "question crop",
    )
    _verify_hash(
        bundle_dir,
        asset.source.crop_path,
        asset.source.sha256,
        "figure crop",
    )
    _verify_optional_hash(
        bundle_dir,
        asset.classification.response_path,
        asset.classification.response_sha256,
        "classification response",
    )
    _verify_optional_hash(
        bundle_dir,
        asset.label_ocr.response_path,
        asset.label_ocr.response_sha256,
        "visible label response",
    )
    return asset


def _validate_crop_relpath(value: str) -> str:
    posix_path = PurePosixPath(value.replace("\\", "/"))
    windows_path = PureWindowsPath(value)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or windows_path.root
        or ".." in posix_path.parts
        or str(posix_path) in {"", "."}
    ):
        raise ValueError("crop_relpath must be a safe relative path")
    return posix_path.as_posix()


def _prompt_version(asset: LabeledFigureAsset, stage: str) -> str:
    if stage == "classification":
        proposal = asset.classification.proposed
        version = proposal.prompt_version if proposal else asset.classification.prompt_version
    else:
        proposal = asset.label_ocr.proposed
        version = proposal.prompt_version if proposal else asset.label_ocr.prompt_version
    if version is None:
        raise ValueError(f"{stage} prompt version is missing")
    return version


def build_reviewed_figure_segment(
    bundle_dir: Path,
    *,
    crop_relpath: str,
) -> ContentSegment:
    safe_crop_relpath = _validate_crop_relpath(crop_relpath)
    asset = load_publishable_asset(bundle_dir)
    reviewed = asset.classification.reviewed
    assert reviewed is not None

    qx1, qy1, qx2, qy2 = asset.source.question_bbox
    fx1, fy1, fx2, fy2 = asset.source.bbox
    if fx2 > qx2 - qx1 or fy2 > qy2 - qy1:
        raise ValueError("figure bbox is outside question crop")

    labels = ", ".join(label.text for label in asset.visible_labels) or "none"
    text = f"{reviewed.visual_family}/{reviewed.subtype}; labels: {labels}"
    classification_version = _prompt_version(asset, "classification")
    label_version = _prompt_version(asset, "label_ocr")

    return ContentSegment(
        kind=SegmentKind.FIGURE,
        text=text,
        source_block_id=asset.asset_id,
        bbox=BBox(qx1 + fx1, qy1 + fy1, qx1 + fx2, qy1 + fy2),
        integrity=IntegrityStatus.OK,
        crop_relpath=safe_crop_relpath,
        version_id=f"figure-b1-v1+{classification_version}+{label_version}",
    )
