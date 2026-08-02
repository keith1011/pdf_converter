from __future__ import annotations

import pytest
from pydantic import ValidationError

from figure_pipeline.classification_models import (
    ClassificationProposal,
    ClassifiedFigureAsset,
    FigureClassification,
    ReviewedClassification,
)
from figure_pipeline.models import FigureAsset

from .helpers import valid_asset_dict


def valid_proposal_dict() -> dict[str, object]:
    return {
        "visual_family": "geometry",
        "subtype": "triangle",
        "secondary_tags": [],
        "confidence": 0.91,
        "evidence": ["The figure contains a triangle with labelled vertices."],
        "needs_review": True,
        "model_id": "Qwen/Qwen3-VL-8B-Instruct",
        "quantization": "4-bit",
        "prompt_version": "figure-b2-v1",
    }


def test_classification_proposal_accepts_compatible_subtype() -> None:
    proposal = ClassificationProposal.model_validate(valid_proposal_dict())

    assert proposal.visual_family == "geometry"
    assert proposal.subtype == "triangle"


def test_classification_proposal_rejects_unknown_subtype() -> None:
    payload = valid_proposal_dict()
    payload["subtype"] = "unknown-subtype"

    with pytest.raises(ValidationError):
        ClassificationProposal.model_validate(payload)


@pytest.mark.parametrize(
    "secondary_tags",
    [
        ["statistical_chart", "statistical_chart"],
        ["unknown"],
    ],
)
def test_classification_proposal_rejects_invalid_secondary_tags(
    secondary_tags: list[str],
) -> None:
    payload = valid_proposal_dict()
    payload["secondary_tags"] = secondary_tags

    with pytest.raises(ValidationError):
        ClassificationProposal.model_validate(payload)


def test_classified_asset_preserves_b1_source_and_unknown_figure_type() -> None:
    payload = valid_asset_dict(
        schema_version="1.1",
        pipeline_version="figure-b2-v1",
        classification={
            "proposed": valid_proposal_dict(),
            "reviewed": None,
            "status": "pending",
        },
    )

    asset = ClassifiedFigureAsset.model_validate(payload)

    assert asset.source.bbox == (700, 350, 1280, 760)
    assert asset.figure_type == "unknown"
    assert asset.schema_version == "1.1"
    assert asset.pipeline_version == "figure-b2-v1"
    assert asset.classification.status == "pending"


def test_rejected_review_requires_unknown_classification() -> None:
    with pytest.raises(ValidationError):
        ReviewedClassification.model_validate(
            {
                "visual_family": "geometry",
                "subtype": "triangle",
                "secondary_tags": [],
                "status": "rejected",
                "reviewer": "human-1",
                "source_proposal_id": "asset:figure-b2-v1",
            }
        )


def test_approved_classification_requires_reviewed_record() -> None:
    proposal = ClassificationProposal.model_validate(valid_proposal_dict())

    with pytest.raises(ValidationError):
        FigureClassification.model_validate(
            {
                "proposed": proposal.model_dump(mode="json"),
                "reviewed": None,
                "status": "approved",
            }
        )


def valid_reviewed_dict(
    *,
    status: str = "approved",
    visual_family: str = "geometry",
    subtype: str = "triangle",
) -> dict[str, object]:
    return {
        "visual_family": visual_family,
        "subtype": subtype,
        "secondary_tags": [],
        "status": status,
        "reviewer": "human-1",
        "source_proposal_id": "asset:figure-b2-v1",
    }


def test_proposal_requires_human_review() -> None:
    payload = valid_proposal_dict()
    payload["needs_review"] = False

    with pytest.raises(ValidationError):
        ClassificationProposal.model_validate(payload)


@pytest.mark.parametrize("evidence", [[""], ["   "]])
def test_proposal_rejects_empty_evidence(evidence: list[str]) -> None:
    payload = valid_proposal_dict()
    payload["evidence"] = evidence

    with pytest.raises(ValidationError):
        ClassificationProposal.model_validate(payload)


def test_pending_classification_requires_proposal() -> None:
    with pytest.raises(ValidationError):
        FigureClassification.model_validate({"status": "pending"})


def test_failed_classification_requires_error() -> None:
    with pytest.raises(ValidationError):
        FigureClassification.model_validate({"status": "failed"})


def test_failed_classification_rejects_reviewed_record() -> None:
    reviewed = valid_reviewed_dict(
        status="rejected",
        visual_family="unknown",
        subtype="unclassified",
    )

    with pytest.raises(ValidationError):
        FigureClassification.model_validate(
            {"status": "failed", "reviewed": reviewed, "error": "parse failed"}
        )


def test_terminal_classification_requires_proposal() -> None:
    with pytest.raises(ValidationError):
        FigureClassification.model_validate(
            {
                "status": "approved",
                "reviewed": valid_reviewed_dict(),
            }
        )


def test_pending_asset_keeps_unknown_figure_type() -> None:
    payload = valid_asset_dict(
        schema_version="1.1",
        pipeline_version="figure-b2-v1",
        figure_type="geometry",
        classification={
            "proposed": valid_proposal_dict(),
            "reviewed": None,
            "status": "pending",
        },
    )

    with pytest.raises(ValidationError):
        ClassifiedFigureAsset.model_validate(payload)


def test_reviewed_asset_figure_type_matches_reviewed_family() -> None:
    classification = {
        "proposed": valid_proposal_dict(),
        "reviewed": valid_reviewed_dict(),
        "status": "approved",
    }
    valid = valid_asset_dict(
        schema_version="1.1",
        pipeline_version="figure-b2-v1",
        figure_type="geometry",
        classification=classification,
    )
    mismatched = {**valid, "figure_type": "unknown"}

    assert ClassifiedFigureAsset.model_validate(valid).figure_type == "geometry"
    with pytest.raises(ValidationError):
        ClassifiedFigureAsset.model_validate(mismatched)


def test_from_b1_preserves_source_and_provenance() -> None:
    b1 = FigureAsset.model_validate(valid_asset_dict())
    classification = FigureClassification.model_validate(
        {
            "proposed": valid_proposal_dict(),
            "reviewed": None,
            "status": "pending",
        }
    )

    b2 = ClassifiedFigureAsset.from_b1(b1, classification)

    assert b2.schema_version == "1.1"
    assert b2.pipeline_version == "figure-b2-v1"
    assert b2.figure_type == "unknown"
    assert b2.source == b1.source
    assert b2.provenance == b1.provenance
