from __future__ import annotations

from pathlib import Path

import pytest

from figure_pipeline.label_ocr_models import ReviewedVisibleLabels, VisibleLabel
from figure_pipeline.label_ocr_review import review_visible_labels_bundle
from figure_pipeline.label_ocr_runner import extract_visible_labels_bundle
from tests.figure_pipeline.test_classification_review import make_approved_b2_bundle
from tests.figure_pipeline.test_label_ocr_runner import (
    VALID_RAW,
    FakeVlmClient,
    load_b3,
    snapshot_tree,
)


def make_pending_b3_bundle(base: Path) -> Path:
    source_b2 = make_approved_b2_bundle(base)
    destination = base / "pending-b3"
    extract_visible_labels_bundle(
        source_b2,
        destination,
        client=FakeVlmClient(VALID_RAW),
    )
    return destination


def make_failed_b3_bundle(base: Path) -> Path:
    source_b2 = make_approved_b2_bundle(base)
    destination = base / "failed-b3"
    extract_visible_labels_bundle(
        source_b2,
        destination,
        client=FakeVlmClient("invalid response"),
    )
    return destination


def source_proposal_id(source_dir: Path) -> str:
    asset = load_b3(source_dir)
    proposal = asset.label_ocr.proposed
    version = proposal.prompt_version if proposal else asset.label_ocr.prompt_version
    assert version is not None
    return f"{asset.asset_id}:{version}"


def test_approved_review_publishes_labels_and_preserves_source(tmp_path: Path) -> None:
    source_dir = make_pending_b3_bundle(tmp_path)
    destination = tmp_path / "approved-b3"
    source_snapshot = snapshot_tree(source_dir)
    source = load_b3(source_dir)
    assert source.label_ocr.proposed is not None
    decision = ReviewedVisibleLabels(
        labels=source.label_ocr.proposed.labels,
        status="approved",
        reviewer="human-b3",
        source_proposal_id=source_proposal_id(source_dir),
    )

    asset = review_visible_labels_bundle(source_dir, destination, decision)

    assert asset.label_ocr.status == "approved"
    assert asset.visible_labels == decision.labels
    assert asset.classification == source.classification
    assert snapshot_tree(source_dir) == source_snapshot
    assert load_b3(destination) == asset


def test_corrected_review_replaces_label_list(tmp_path: Path) -> None:
    source_dir = make_pending_b3_bundle(tmp_path)
    destination = tmp_path / "corrected-b3"
    labels = [
        VisibleLabel(text="A", kind="latin_letter"),
        VisibleLabel(text="α", kind="greek_letter"),
    ]
    decision = ReviewedVisibleLabels(
        labels=labels,
        status="corrected",
        reviewer="human-b3",
        source_proposal_id=source_proposal_id(source_dir),
    )

    asset = review_visible_labels_bundle(source_dir, destination, decision)

    assert asset.label_ocr.status == "corrected"
    assert asset.visible_labels == labels


def test_rejected_review_keeps_visible_labels_empty(tmp_path: Path) -> None:
    source_dir = make_pending_b3_bundle(tmp_path)
    destination = tmp_path / "rejected-b3"
    decision = ReviewedVisibleLabels(
        labels=[],
        status="rejected",
        reviewer="human-b3",
        source_proposal_id=source_proposal_id(source_dir),
    )

    asset = review_visible_labels_bundle(source_dir, destination, decision)

    assert asset.label_ocr.status == "rejected"
    assert asset.visible_labels == []


def test_failed_source_can_be_corrected_with_raw_response_preserved(
    tmp_path: Path,
) -> None:
    source_dir = make_failed_b3_bundle(tmp_path)
    destination = tmp_path / "failed-corrected-b3"
    source = load_b3(source_dir)
    source_snapshot = snapshot_tree(source_dir)
    labels = [VisibleLabel(text="B", kind="latin_letter")]
    decision = ReviewedVisibleLabels(
        labels=labels,
        status="corrected",
        reviewer="human-b3",
        source_proposal_id=source_proposal_id(source_dir),
    )

    asset = review_visible_labels_bundle(source_dir, destination, decision)

    assert asset.label_ocr.status == "corrected"
    assert asset.visible_labels == labels
    assert asset.label_ocr.response_sha256 == source.label_ocr.response_sha256
    assert snapshot_tree(source_dir) == source_snapshot
    assert (destination / "visible_label_response.txt").read_bytes() == source_snapshot[
        "visible_label_response.txt"
    ]


def test_failed_source_approved_review_is_rejected(tmp_path: Path) -> None:
    source_dir = make_failed_b3_bundle(tmp_path)
    destination = tmp_path / "failed-approved-b3"
    decision = ReviewedVisibleLabels(
        labels=[],
        status="approved",
        reviewer="human-b3",
        source_proposal_id=source_proposal_id(source_dir),
    )

    with pytest.raises(ValueError, match="approved label review requires a proposal"):
        review_visible_labels_bundle(source_dir, destination, decision)

    assert not destination.exists()


def test_failed_source_response_hash_mismatch_fails_before_copy(tmp_path: Path) -> None:
    source_dir = make_failed_b3_bundle(tmp_path)
    (source_dir / "visible_label_response.txt").write_text("tampered", encoding="utf-8")
    destination = tmp_path / "tampered-review"
    decision = ReviewedVisibleLabels(
        labels=[VisibleLabel(text="A", kind="latin_letter")],
        status="corrected",
        reviewer="human-b3",
        source_proposal_id=source_proposal_id(source_dir),
    )

    with pytest.raises(ValueError, match="visible label response hash"):
        review_visible_labels_bundle(source_dir, destination, decision)

    assert not destination.exists()
