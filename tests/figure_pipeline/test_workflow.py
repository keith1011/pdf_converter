from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from figure_pipeline.classification_models import ReviewedClassification
from figure_pipeline.classification_review import review_bundle
from figure_pipeline.label_ocr_models import ReviewedVisibleLabels
from figure_pipeline.label_ocr_review import review_visible_labels_bundle
from figure_pipeline.proposal import create_proposal_bundle
from figure_pipeline.workflow import WorkflowPaths, inspect_workflow
from tests.figure_pipeline.test_classification_review import (
    make_pending_b2_bundle,
    proposal_id,
)
from tests.figure_pipeline.test_classification_runner import make_b1_bundle
from tests.figure_pipeline.test_label_ocr_review import (
    make_pending_b3_bundle,
    source_proposal_id,
)
from tests.figure_pipeline.test_label_ocr_runner import load_b3
from tests.figure_pipeline.test_preserve import make_source
from tests.figure_pipeline.test_proposal import FakeDetector


def _copy_bundle(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _place_b1(paths: WorkflowPaths, tmp_path: Path) -> None:
    _copy_bundle(make_b1_bundle(tmp_path / "source-b1"), paths.b1_asset)


def _place_pending_b2(paths: WorkflowPaths, tmp_path: Path) -> Path:
    _place_b1(paths, tmp_path)
    pending = make_pending_b2_bundle(tmp_path / "source-b2")
    _copy_bundle(pending, paths.b2_proposal)
    return paths.b2_proposal


def _place_reviewed_b2(
    paths: WorkflowPaths,
    tmp_path: Path,
    *,
    status: str = "approved",
) -> None:
    pending = _place_pending_b2(paths, tmp_path)
    decision = ReviewedClassification(
        visual_family="geometry" if status != "rejected" else "unknown",
        subtype="triangle" if status != "rejected" else "unclassified",
        secondary_tags=[],
        status=status,
        reviewer="workflow-human",
        source_proposal_id=proposal_id(pending),
    )
    review_bundle(pending, paths.b2_reviewed, decision)


def _place_pending_b3(paths: WorkflowPaths, tmp_path: Path) -> Path:
    _place_reviewed_b2(paths, tmp_path)
    pending = make_pending_b3_bundle(tmp_path / "source-b3")
    _copy_bundle(pending, paths.b3_proposal)
    return paths.b3_proposal


def _place_reviewed_b3(
    paths: WorkflowPaths,
    tmp_path: Path,
    *,
    status: str = "approved",
) -> None:
    pending = _place_pending_b3(paths, tmp_path)
    asset = load_b3(pending)
    assert asset.label_ocr.proposed is not None
    labels = asset.label_ocr.proposed.labels if status != "rejected" else []
    decision = ReviewedVisibleLabels(
        labels=labels,
        status=status,
        reviewer="workflow-human",
        source_proposal_id=source_proposal_id(pending),
    )
    review_visible_labels_bundle(pending, paths.b3_reviewed, decision)


def test_empty_workflow_needs_b1_proposal(tmp_path: Path) -> None:
    status = inspect_workflow(tmp_path / "q018")

    assert status.state == "needs_b1_proposal"
    assert status.next_command == "b1-propose"


def test_b1_asset_is_ready_for_b2(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_b1(paths, tmp_path)

    status = inspect_workflow(paths.root)

    assert status.state == "ready_for_b2"
    assert status.next_command == "b2-propose"


def test_b2_proposal_stops_for_human_review(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_pending_b2(paths, tmp_path)

    status = inspect_workflow(paths.root)

    assert status.state == "awaiting_b2_review"
    assert status.next_command == "b2-review"


def test_b2_reviewed_is_ready_for_b3(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_reviewed_b2(paths, tmp_path)

    status = inspect_workflow(paths.root)

    assert status.state == "ready_for_b3"
    assert status.next_command == "b3-propose"


def test_b3_proposal_stops_for_human_review(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_pending_b3(paths, tmp_path)

    status = inspect_workflow(paths.root)

    assert status.state == "awaiting_b3_review"
    assert status.next_command == "b3-review"


def test_b3_reviewed_is_ready_for_assembly(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_reviewed_b3(paths, tmp_path)

    status = inspect_workflow(paths.root)

    assert status.state == "ready_for_assembly"
    assert status.next_command == "assemble"


@pytest.mark.parametrize("stage", ["b2", "b3"])
def test_rejected_review_blocks_workflow(tmp_path: Path, stage: str) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    if stage == "b2":
        _place_reviewed_b2(paths, tmp_path, status="rejected")
    else:
        _place_reviewed_b3(paths, tmp_path, status="rejected")

    status = inspect_workflow(paths.root)

    assert status.state == "blocked_rejected"
    assert status.next_command is None


def test_downstream_stage_gap_is_rejected(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    pending = make_pending_b2_bundle(tmp_path / "source-b2")
    _copy_bundle(pending, paths.b2_proposal)

    with pytest.raises(ValueError, match="b1-asset"):
        inspect_workflow(paths.root)


def test_tampered_crop_is_rejected(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_b1(paths, tmp_path)
    payload = json.loads((paths.b1_asset / "figure_asset.json").read_text(encoding="utf-8"))
    crop = paths.b1_asset / payload["source"]["crop_path"]
    crop.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="hash"):
        inspect_workflow(paths.root)


def test_b1_proposal_awaits_candidate_selection(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    create_proposal_bundle(
        source=make_source(tmp_path),
        detector=FakeDetector(),
        destination=paths.b1_proposal,
    )

    status = inspect_workflow(paths.root)

    assert status.state == "awaiting_b1_selection"
    assert status.next_command == "b1-preserve"


def test_nonempty_assembled_stage_finishes_workflow(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_reviewed_b3(paths, tmp_path)
    from figure_pipeline.publish import publish_reviewed_figures
    from tests.figure_pipeline.test_publish import _write_pageir

    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    publish_reviewed_figures(
        pageir_path=pageir_path,
        bundle_dirs=[paths.b3_reviewed],
        destination=paths.assembled,
    )

    status = inspect_workflow(paths.root)

    assert status.state == "assembled"
    assert status.next_command is None


def test_assembled_stage_requires_pageir_artifact(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_reviewed_b3(paths, tmp_path)
    paths.assembled.mkdir()
    (paths.assembled / "sentinel.bin").write_bytes(b"not-pageir")

    with pytest.raises(ValueError, match="PageIR"):
        inspect_workflow(paths.root)


def test_assembled_stage_rejects_invalid_pageir_json(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_reviewed_b3(paths, tmp_path)
    paths.assembled.mkdir()
    (paths.assembled / "2015p2.pageir.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="PageIR"):
        inspect_workflow(paths.root)


def test_cross_stage_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _copy_bundle(
        make_b1_bundle(tmp_path / "source-b1-q019", question=19),
        paths.b1_asset,
    )
    _copy_bundle(
        make_pending_b2_bundle(tmp_path / "source-b2-q018"),
        paths.b2_proposal,
    )

    with pytest.raises(ValueError, match="identity"):
        inspect_workflow(paths.root)


def test_cross_stage_crop_binding_mismatch_is_rejected(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_b1(paths, tmp_path)
    pending = make_pending_b2_bundle(tmp_path / "source-b2")
    metadata_path = pending / "figure_asset.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    crop = pending / payload["source"]["crop_path"]
    crop.write_bytes(b"different-but-internally-valid-crop")
    from figure_pipeline.proposal import sha256_file

    payload["source"]["sha256"] = sha256_file(crop)
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")
    _copy_bundle(pending, paths.b2_proposal)

    with pytest.raises(ValueError, match="identity"):
        inspect_workflow(paths.root)


def test_malformed_b1_asset_fails_before_downstream_output(tmp_path: Path) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_b1(paths, tmp_path)
    (paths.b1_asset / "figure_asset.json").write_text("{", encoding="utf-8")

    with pytest.raises(ValidationError):
        inspect_workflow(paths.root)

    downstream = (
        paths.b2_proposal,
        paths.b2_reviewed,
        paths.b3_proposal,
        paths.b3_reviewed,
        paths.assembled,
    )
    assert not any(path.exists() for path in downstream)
