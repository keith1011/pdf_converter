from __future__ import annotations

import json
from pathlib import Path

import pytest

from figure_pipeline.label_ocr_models import ReviewedVisibleLabels, VisibleLabel
from figure_pipeline.label_ocr_review import review_visible_labels_bundle
from figure_pipeline.models import resolve_bundle_path
from figure_pipeline.pageir import (
    build_reviewed_figure_segment,
    load_publishable_asset,
)
from ocr_pipeline.models import SegmentKind
from tests.figure_pipeline.test_label_ocr_review import (
    make_pending_b3_bundle,
    source_proposal_id,
)
from tests.figure_pipeline.test_label_ocr_runner import load_b3


def make_reviewed_b3_bundle(
    base: Path,
    *,
    status: str = "corrected",
) -> Path:
    pending = make_pending_b3_bundle(base)
    destination = base / f"{status}-b3"
    pending_asset = load_b3(pending)
    assert pending_asset.label_ocr.proposed is not None
    if status == "approved":
        labels = pending_asset.label_ocr.proposed.labels
    elif status == "corrected":
        labels = [
            VisibleLabel(text="A", kind="latin_letter"),
            VisibleLabel(text="B", kind="latin_letter"),
        ]
    else:
        labels = []
    decision = ReviewedVisibleLabels(
        labels=labels,
        status=status,
        reviewer="pageir-human",
        source_proposal_id=source_proposal_id(pending),
    )
    review_visible_labels_bundle(pending, destination, decision)
    return destination


def test_pending_b3_is_not_publishable(tmp_path: Path) -> None:
    bundle = make_pending_b3_bundle(tmp_path)

    with pytest.raises(ValueError, match="human-reviewed"):
        load_publishable_asset(bundle)


@pytest.mark.parametrize("status", ["approved", "corrected"])
def test_reviewed_b2_and_b3_are_publishable(tmp_path: Path, status: str) -> None:
    bundle = make_reviewed_b3_bundle(tmp_path, status=status)

    assert load_publishable_asset(bundle).label_ocr.status == status


def test_rejected_b3_is_not_publishable(tmp_path: Path) -> None:
    bundle = make_reviewed_b3_bundle(tmp_path, status="rejected")

    with pytest.raises(ValueError, match="rejected"):
        load_publishable_asset(bundle)


def test_missing_or_tampered_crop_is_not_publishable(tmp_path: Path) -> None:
    missing_bundle = make_reviewed_b3_bundle(tmp_path / "missing")
    missing_asset = load_publishable_asset(missing_bundle)
    resolve_bundle_path(missing_bundle, missing_asset.source.crop_path).unlink()

    with pytest.raises(ValueError, match="figure crop hash"):
        load_publishable_asset(missing_bundle)

    tampered_bundle = make_reviewed_b3_bundle(tmp_path / "tampered")
    tampered_asset = load_publishable_asset(tampered_bundle)
    resolve_bundle_path(tampered_bundle, tampered_asset.source.crop_path).write_bytes(
        b"tampered"
    )

    with pytest.raises(ValueError, match="figure crop hash"):
        load_publishable_asset(tampered_bundle)


def test_reviewed_asset_maps_deterministically_to_pageir(tmp_path: Path) -> None:
    bundle = make_reviewed_b3_bundle(tmp_path)
    asset = load_publishable_asset(bundle)

    segment = build_reviewed_figure_segment(
        bundle,
        crop_relpath=(
            "figures/hk-dse-2015-math-p2-q018-fig01-a1b2c3d4e5f6.png"
        ),
    )

    qx1, qy1, _, _ = asset.source.question_bbox
    fx1, fy1, fx2, fy2 = asset.source.bbox
    assert segment.kind is SegmentKind.FIGURE
    assert segment.source_block_id == "hk-dse-2015-math-p2-q018-fig01"
    assert segment.bbox.as_int_tuple() == (
        qx1 + fx1,
        qy1 + fy1,
        qx1 + fx2,
        qy1 + fy2,
    )
    assert segment.text == "geometry/triangle; labels: A, B"
    assert segment.version_id == "figure-b1-v1+figure-b2-v1+figure-b3-v3"


def test_pageir_mapping_rejects_unsafe_crop_relpath(tmp_path: Path) -> None:
    bundle = make_reviewed_b3_bundle(tmp_path)

    with pytest.raises(ValueError, match="relative"):
        build_reviewed_figure_segment(bundle, crop_relpath="../escape.png")


def test_question_bbox_cannot_be_smaller_than_figure_bbox(tmp_path: Path) -> None:
    bundle = make_reviewed_b3_bundle(tmp_path)
    metadata_path = bundle / "figure_asset.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload["source"]["question_bbox"] = [0, 0, 10, 10]
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="outside question crop"):
        build_reviewed_figure_segment(bundle, crop_relpath="figures/safe.png")


@pytest.mark.parametrize("review_stage", ["classification", "label_ocr"])
def test_publishable_asset_revalidates_review_proposal_binding(
    tmp_path: Path,
    review_stage: str,
) -> None:
    bundle = make_reviewed_b3_bundle(tmp_path, status="approved")
    metadata_path = bundle / "figure_asset.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload[review_stage]["reviewed"]["source_proposal_id"] = "forged:proposal"
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="proposal"):
        load_publishable_asset(bundle)
