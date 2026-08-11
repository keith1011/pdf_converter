from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .classification_models import ClassifiedFigureAsset
from .label_ocr_models import LabeledFigureAsset
from .models import FigureAsset, ProposalBundle, StrictModel, resolve_bundle_path
from .proposal import sha256_file

WorkflowState = Literal[
    "needs_b1_proposal",
    "awaiting_b1_selection",
    "ready_for_b2",
    "awaiting_b2_review",
    "ready_for_b3",
    "awaiting_b3_review",
    "ready_for_assembly",
    "blocked_rejected",
    "assembled",
]


class WorkflowStatus(StrictModel):
    state: WorkflowState
    next_command: str | None
    reason: str


@dataclass(frozen=True)
class WorkflowPaths:
    root: Path
    b1_proposal: Path
    b1_asset: Path
    b2_proposal: Path
    b2_reviewed: Path
    b3_proposal: Path
    b3_reviewed: Path
    assembled: Path

    @classmethod
    def for_root(cls, root: Path) -> WorkflowPaths:
        return cls(
            root=root,
            b1_proposal=root / "b1-proposal",
            b1_asset=root / "b1-asset",
            b2_proposal=root / "b2-proposal",
            b2_reviewed=root / "b2-reviewed",
            b3_proposal=root / "b3-proposal",
            b3_reviewed=root / "b3-reviewed",
            assembled=root / "assembled",
        )


def _require_directory(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"workflow stage is not a directory: {path.name}")


def _require_upstream(path: Path) -> None:
    if not path.is_dir():
        raise ValueError(f"workflow stage requires {path.name}")


def _verify_hash(root: Path, relative_path: str, expected: str, label: str) -> None:
    path = resolve_bundle_path(root, relative_path)
    if not path.is_file() or sha256_file(path) != expected:
        raise ValueError(f"{label} hash mismatch")


def _validate_common_asset(root: Path, asset: FigureAsset) -> None:
    _verify_hash(
        root,
        asset.source.question_crop_path,
        asset.source.question_crop_sha256,
        "question crop",
    )
    _verify_hash(root, asset.source.crop_path, asset.source.sha256, "figure crop")


def _load_b1(path: Path) -> FigureAsset:
    asset = FigureAsset.model_validate_json(
        (path / "figure_asset.json").read_text(encoding="utf-8")
    )
    _validate_common_asset(path, asset)
    return asset


def _load_b2(path: Path) -> ClassifiedFigureAsset:
    asset = ClassifiedFigureAsset.model_validate_json(
        (path / "figure_asset.json").read_text(encoding="utf-8")
    )
    _validate_common_asset(path, asset)
    if asset.classification.response_path is not None:
        assert asset.classification.response_sha256 is not None
        _verify_hash(
            path,
            asset.classification.response_path,
            asset.classification.response_sha256,
            "classification response",
        )
    return asset


def _load_b3(path: Path) -> LabeledFigureAsset:
    asset = LabeledFigureAsset.model_validate_json(
        (path / "figure_asset.json").read_text(encoding="utf-8")
    )
    _validate_common_asset(path, asset)
    if asset.classification.response_path is not None:
        assert asset.classification.response_sha256 is not None
        _verify_hash(
            path,
            asset.classification.response_path,
            asset.classification.response_sha256,
            "classification response",
        )
    if asset.label_ocr.response_path is not None:
        assert asset.label_ocr.response_sha256 is not None
        _verify_hash(
            path,
            asset.label_ocr.response_path,
            asset.label_ocr.response_sha256,
            "visible label response",
        )
    return asset


def _validate_identity(*assets: FigureAsset) -> None:
    first = assets[0]
    for asset in assets[1:]:
        if (
            asset.document_id != first.document_id
            or asset.parent_question_id != first.parent_question_id
            or asset.asset_id != first.asset_id
            or asset.source != first.source
            or asset.provenance != first.provenance
        ):
            raise ValueError("Figure identity mismatch across workflow stages")


def _validate_assembled(path: Path, asset: LabeledFigureAsset) -> None:
    pageir_files = list(path.glob("*.pageir.json"))
    if len(pageir_files) != 1:
        raise ValueError("assembled stage requires exactly one PageIR artifact")
    try:
        payload = json.loads(pageir_files[0].read_text(encoding="utf-8"))
        pages = payload["pages"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("assembled PageIR artifact is invalid") from exc
    if not isinstance(pages, list):
        raise ValueError("assembled PageIR artifact is invalid")
    matches: list[dict] = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("segments"), list):
            raise ValueError("assembled PageIR artifact is invalid")
        for segment in page["segments"]:
            if isinstance(segment, dict) and segment.get("source_block_id") == asset.asset_id:
                matches.append(segment)
    if len(matches) != 1 or matches[0].get("kind") != "figure":
        raise ValueError("assembled PageIR is missing the reviewed Figure segment")
    crop_relpath = matches[0].get("crop_relpath")
    if not isinstance(crop_relpath, str):
        raise ValueError("assembled PageIR Figure crop path is invalid")
    _verify_hash(path, crop_relpath, asset.source.sha256, "assembled figure crop")


def _validate_b1_proposal(path: Path) -> None:
    ProposalBundle.model_validate_json(
        (path / "proposal.json").read_text(encoding="utf-8")
    )
    if not (path / "proposal_overlay.png").is_file():
        raise ValueError("b1-proposal is missing proposal_overlay.png")


def inspect_workflow(root: Path) -> WorkflowStatus:
    paths = WorkflowPaths.for_root(root)
    stages = (
        paths.b1_proposal,
        paths.b1_asset,
        paths.b2_proposal,
        paths.b2_reviewed,
        paths.b3_proposal,
        paths.b3_reviewed,
        paths.assembled,
    )
    for stage in stages:
        _require_directory(stage)

    if paths.assembled.exists():
        _require_upstream(paths.b1_asset)
        _require_upstream(paths.b2_proposal)
        _require_upstream(paths.b2_reviewed)
        _require_upstream(paths.b3_proposal)
        _require_upstream(paths.b3_reviewed)
        b1_asset = _load_b1(paths.b1_asset)
        b2_proposal = _load_b2(paths.b2_proposal)
        b2_reviewed = _load_b2(paths.b2_reviewed)
        b3_proposal = _load_b3(paths.b3_proposal)
        asset = _load_b3(paths.b3_reviewed)
        _validate_identity(b1_asset, b2_proposal, b2_reviewed, b3_proposal, asset)
        if asset.classification.status not in {"approved", "corrected"}:
            raise ValueError("assembled stage requires reviewed B2 classification")
        if asset.label_ocr.status not in {"approved", "corrected"}:
            raise ValueError("assembled stage requires reviewed B3 labels")
        _validate_assembled(paths.assembled, asset)
        return WorkflowStatus(
            state="assembled",
            next_command=None,
            reason="reviewed figure has been assembled into PageIR",
        )

    if paths.b3_reviewed.exists():
        _require_upstream(paths.b3_proposal)
        _require_upstream(paths.b2_reviewed)
        _require_upstream(paths.b2_proposal)
        _require_upstream(paths.b1_asset)
        b1_asset = _load_b1(paths.b1_asset)
        b2_proposal = _load_b2(paths.b2_proposal)
        b2_reviewed = _load_b2(paths.b2_reviewed)
        b3_proposal = _load_b3(paths.b3_proposal)
        asset = _load_b3(paths.b3_reviewed)
        _validate_identity(b1_asset, b2_proposal, b2_reviewed, b3_proposal, asset)
        if asset.label_ocr.status == "rejected":
            return WorkflowStatus(
                state="blocked_rejected",
                next_command=None,
                reason="B3 visible-label review rejected the figure",
            )
        if asset.classification.status not in {"approved", "corrected"}:
            raise ValueError("b3-reviewed requires approved or corrected B2")
        if asset.label_ocr.status not in {"approved", "corrected"}:
            raise ValueError("b3-reviewed requires an explicit human review")
        return WorkflowStatus(
            state="ready_for_assembly",
            next_command="assemble",
            reason="B2 and B3 reviews are publishable",
        )

    if paths.b3_proposal.exists():
        _require_upstream(paths.b2_reviewed)
        _require_upstream(paths.b2_proposal)
        _require_upstream(paths.b1_asset)
        b1_asset = _load_b1(paths.b1_asset)
        b2_proposal = _load_b2(paths.b2_proposal)
        b2_reviewed = _load_b2(paths.b2_reviewed)
        asset = _load_b3(paths.b3_proposal)
        _validate_identity(b1_asset, b2_proposal, b2_reviewed, asset)
        if asset.classification.status not in {"approved", "corrected"}:
            raise ValueError("b3-proposal requires approved or corrected B2")
        if asset.label_ocr.status not in {"pending", "failed"}:
            raise ValueError("b3-proposal must await human review")
        return WorkflowStatus(
            state="awaiting_b3_review",
            next_command="b3-review",
            reason="B3 proposal requires explicit human review",
        )

    if paths.b2_reviewed.exists():
        _require_upstream(paths.b2_proposal)
        _require_upstream(paths.b1_asset)
        b1_asset = _load_b1(paths.b1_asset)
        b2_proposal = _load_b2(paths.b2_proposal)
        asset = _load_b2(paths.b2_reviewed)
        _validate_identity(b1_asset, b2_proposal, asset)
        if asset.classification.status == "rejected":
            return WorkflowStatus(
                state="blocked_rejected",
                next_command=None,
                reason="B2 classification review rejected the figure",
            )
        if asset.classification.status not in {"approved", "corrected"}:
            raise ValueError("b2-reviewed requires an explicit human review")
        return WorkflowStatus(
            state="ready_for_b3",
            next_command="b3-propose",
            reason="B2 review is publishable",
        )

    if paths.b2_proposal.exists():
        _require_upstream(paths.b1_asset)
        b1_asset = _load_b1(paths.b1_asset)
        asset = _load_b2(paths.b2_proposal)
        _validate_identity(b1_asset, asset)
        if asset.classification.status not in {"pending", "failed"}:
            raise ValueError("b2-proposal must await human review")
        return WorkflowStatus(
            state="awaiting_b2_review",
            next_command="b2-review",
            reason="B2 proposal requires explicit human review",
        )

    if paths.b1_asset.exists():
        _load_b1(paths.b1_asset)
        return WorkflowStatus(
            state="ready_for_b2",
            next_command="b2-propose",
            reason="B1 asset is preserved and hash-verified",
        )

    if paths.b1_proposal.exists():
        _validate_b1_proposal(paths.b1_proposal)
        return WorkflowStatus(
            state="awaiting_b1_selection",
            next_command="b1-preserve",
            reason="B1 proposal requires candidate selection or a manual bbox",
        )

    return WorkflowStatus(
        state="needs_b1_proposal",
        next_command="b1-propose",
        reason="no Figure workflow stage exists",
    )
