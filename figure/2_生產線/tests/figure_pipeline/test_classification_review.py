from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from PIL import Image

import figure_pipeline.classification_review as review_module
from figure_pipeline.classification_models import (
    ClassificationProposal,
    ClassifiedFigureAsset,
    FigureClassification,
    ReviewedClassification,
)
from figure_pipeline.classification_review import review_bundle
from figure_pipeline.models import FigureAsset
from figure_pipeline.proposal import sha256_file
from tests.figure_pipeline.helpers import valid_asset_dict


def valid_proposal(
    *,
    secondary_tags: list[str] | None = None,
) -> ClassificationProposal:
    return ClassificationProposal(
        visual_family="geometry",
        subtype="triangle",
        secondary_tags=secondary_tags or [],
        confidence=0.91,
        evidence=["Three visible straight edges form a triangle"],
        needs_review=True,
        model_id="Qwen/Qwen3-VL-8B-Instruct",
        quantization="4-bit",
        prompt_version="figure-b2-v1",
    )


def snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def write_asset(path: Path, asset: ClassifiedFigureAsset) -> None:
    payload = json.dumps(
        asset.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    path.write_bytes((payload + chr(10)).encode("utf-8"))


def load_asset(source_dir: Path) -> ClassifiedFigureAsset:
    return ClassifiedFigureAsset.model_validate_json(
        (source_dir / "figure_asset.json").read_text(encoding="utf-8")
    )


def make_pending_b2_bundle(
    base: Path,
    *,
    secondary_tags: list[str] | None = None,
) -> Path:
    source_dir = base / "pending-b2"
    asset_dir = source_dir / "assets"
    asset_dir.mkdir(parents=True)
    crop_path = asset_dir / "q018_fig01.png"
    Image.new("RGB", (16, 12), color="white").save(crop_path)
    question_path = source_dir / "question.png"
    Image.new("RGB", (24, 20), color="white").save(question_path)
    (source_dir / "audit-sidecar.bin").write_bytes(b"pending-b2-sidecar")

    payload = valid_asset_dict()
    payload["source"]["sha256"] = sha256_file(crop_path)
    payload["source"]["question_crop_sha256"] = sha256_file(question_path)
    b1 = FigureAsset.model_validate(payload)
    pending = ClassifiedFigureAsset.from_b1(
        b1,
        FigureClassification(
            status="pending",
            proposed=valid_proposal(secondary_tags=secondary_tags),
        ),
    )
    write_asset(source_dir / "figure_asset.json", pending)
    return source_dir


def proposal_id(source_dir: Path) -> str:
    asset = load_asset(source_dir)
    assert asset.classification.proposed is not None
    return f"{asset.asset_id}:{asset.classification.proposed.prompt_version}"


def approved_decision(source_dir: Path) -> ReviewedClassification:
    asset = load_asset(source_dir)
    proposal = asset.classification.proposed
    assert proposal is not None
    return ReviewedClassification(
        visual_family=proposal.visual_family,
        subtype=proposal.subtype,
        secondary_tags=proposal.secondary_tags,
        status="approved",
        reviewer="human-1",
        source_proposal_id=proposal_id(source_dir),
    )


def make_approved_b2_bundle(base: Path) -> Path:
    source_dir = make_pending_b2_bundle(base)
    pending = load_asset(source_dir)
    decision = approved_decision(source_dir)
    classification_payload = pending.classification.model_dump(mode="json")
    classification_payload.update(
        {
            "reviewed": decision.model_dump(mode="json"),
            "status": "approved",
        }
    )
    payload = pending.model_dump(mode="json")
    payload.update(
        {
            "figure_type": "geometry",
            "classification": FigureClassification.model_validate(
                classification_payload
            ).model_dump(mode="json"),
        }
    )
    write_asset(
        source_dir / "figure_asset.json",
        ClassifiedFigureAsset.model_validate(payload),
    )
    return source_dir


def test_approve_derives_figure_type_and_preserves_whole_source(
    tmp_path: Path,
) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    destination = tmp_path / "approved"
    source_snapshot = snapshot_tree(source_dir)

    asset = review_bundle(
        source_dir,
        destination,
        approved_decision(source_dir),
    )

    assert asset.figure_type == "geometry"
    assert asset.classification.status == "approved"
    assert asset.classification.reviewed is not None
    assert asset.classification.reviewed.reviewer == "human-1"
    assert asset.validation.reviewed is False
    assert snapshot_tree(source_dir) == source_snapshot
    assert (destination / "assets/q018_fig01.png").read_bytes() == source_snapshot[
        "assets/q018_fig01.png"
    ]
    assert (destination / "audit-sidecar.bin").read_bytes() == source_snapshot["audit-sidecar.bin"]
    destination_snapshot = snapshot_tree(destination)
    for relative_path, content in source_snapshot.items():
        if relative_path != "figure_asset.json":
            assert destination_snapshot[relative_path] == content
    assert load_asset(destination) == asset


def test_approved_review_accepts_equivalent_reordered_secondary_tags(
    tmp_path: Path,
) -> None:
    source_dir = make_pending_b2_bundle(
        tmp_path,
        secondary_tags=["statistical_chart", "table"],
    )
    destination = tmp_path / "approved-reordered-tags"
    decision = ReviewedClassification(
        visual_family="geometry",
        subtype="triangle",
        secondary_tags=["table", "statistical_chart"],
        status="approved",
        reviewer="human-tags",
        source_proposal_id=proposal_id(source_dir),
    )

    asset = review_bundle(source_dir, destination, decision)

    assert asset.classification.status == "approved"
    assert asset.classification.reviewed == decision


def test_corrected_review_replaces_semantics_without_mutating_source(
    tmp_path: Path,
) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    destination = tmp_path / "corrected"
    original = load_asset(source_dir)
    decision = ReviewedClassification(
        visual_family="coordinate_graph",
        subtype="point_plot",
        secondary_tags=["geometry"],
        status="corrected",
        reviewer="human-2",
        source_proposal_id=proposal_id(source_dir),
    )

    asset = review_bundle(source_dir, destination, decision)

    assert asset.figure_type == "coordinate_graph"
    assert asset.classification.status == "corrected"
    assert asset.classification.proposed == original.classification.proposed
    assert asset.classification.reviewed == decision
    assert load_asset(source_dir) == original


def test_rejected_review_uses_unknown_and_stays_unresolved(tmp_path: Path) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    destination = tmp_path / "rejected"
    decision = ReviewedClassification(
        visual_family="unknown",
        subtype="unclassified",
        secondary_tags=[],
        status="rejected",
        reviewer="human-3",
        source_proposal_id=proposal_id(source_dir),
    )

    asset = review_bundle(source_dir, destination, decision)

    assert asset.figure_type == "unknown"
    assert asset.classification.status == "rejected"
    assert asset.classification.reviewed == decision


def test_review_requires_pending_proposal(tmp_path: Path) -> None:
    source_dir = make_approved_b2_bundle(tmp_path)
    destination = tmp_path / "invalid-review"

    with pytest.raises(ValueError, match="pending"):
        review_bundle(
            source_dir,
            destination,
            approved_decision(source_dir),
        )

    assert not destination.exists()
    assert list(tmp_path.glob(".invalid-review.staging-*")) == []


def test_existing_destination_is_preserved_before_source_validation(
    tmp_path: Path,
) -> None:
    source_dir = make_approved_b2_bundle(tmp_path)
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "sentinel.bin"
    sentinel.write_bytes(b"do-not-touch")

    with pytest.raises(FileExistsError):
        review_bundle(source_dir, destination, approved_decision(source_dir))

    assert sentinel.read_bytes() == b"do-not-touch"


def test_review_requires_matching_source_proposal_id(tmp_path: Path) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    destination = tmp_path / "wrong-proposal"
    decision = approved_decision(source_dir).model_copy(
        update={"source_proposal_id": "wrong:figure-b2-v1"}
    )

    with pytest.raises(ValueError, match="proposal"):
        review_bundle(source_dir, destination, decision)

    assert not destination.exists()
    assert list(tmp_path.glob(".wrong-proposal.staging-*")) == []


@pytest.mark.parametrize(
    ("visual_family", "subtype", "secondary_tags"),
    [
        ("geometry", "circle", []),
        ("geometry", "triangle", ["statistical_chart"]),
        ("coordinate_graph", "point_plot", []),
    ],
)
def test_approved_decision_must_match_original_proposal(
    tmp_path: Path,
    visual_family: str,
    subtype: str,
    secondary_tags: list[str],
) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    destination = tmp_path / "false-approval"
    decision = ReviewedClassification.model_validate(
        {
            "visual_family": visual_family,
            "subtype": subtype,
            "secondary_tags": secondary_tags,
            "status": "approved",
            "reviewer": "human-4",
            "source_proposal_id": proposal_id(source_dir),
        }
    )

    with pytest.raises(ValueError, match="approved"):
        review_bundle(source_dir, destination, decision)

    assert not destination.exists()


def test_source_crop_hash_mismatch_fails_before_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    (source_dir / "assets/q018_fig01.png").write_bytes(b"tampered")
    destination = tmp_path / "reviewed"
    copy_calls: list[tuple[Path, Path]] = []
    original_copytree = review_module.shutil.copytree

    def record_copytree(source: Path, target: Path, **kwargs: object) -> Path:
        copy_calls.append((source, target))
        return original_copytree(source, target, **kwargs)

    monkeypatch.setattr(review_module.shutil, "copytree", record_copytree)

    with pytest.raises(ValueError, match="hash"):
        review_bundle(source_dir, destination, approved_decision(source_dir))

    assert copy_calls == []
    assert not destination.exists()
    assert list(tmp_path.glob(".reviewed.staging-*")) == []


def test_rename_failure_removes_only_operation_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    source_snapshot = snapshot_tree(source_dir)
    destination = tmp_path / "approved"

    def fail_rename(source: Path, target: Path) -> Path:
        raise OSError(f"rename failed: {source} -> {target}")

    monkeypatch.setattr(Path, "rename", fail_rename)

    with pytest.raises(OSError, match="rename failed"):
        review_bundle(source_dir, destination, approved_decision(source_dir))

    assert snapshot_tree(source_dir) == source_snapshot
    assert not destination.exists()
    assert list(tmp_path.glob(".approved.staging-*")) == []


def test_review_renames_sibling_uuid_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    destination = tmp_path / "approved"
    rename_calls: list[tuple[Path, Path]] = []
    original_rename = Path.rename

    def record_rename(source: Path, target: Path) -> Path:
        rename_calls.append((source, target))
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", record_rename)

    review_bundle(source_dir, destination, approved_decision(source_dir))

    assert len(rename_calls) == 1
    stage, target = rename_calls[0]
    assert stage.parent == destination.parent
    assert re.fullmatch(r"\.approved\.staging-[0-9a-f]{32}", stage.name)
    assert target == destination
    assert not stage.exists()
