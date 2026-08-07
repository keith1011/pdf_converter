from __future__ import annotations

import pytest
from pydantic import ValidationError

from figure_pipeline.classification_models import ClassifiedFigureAsset
from figure_pipeline.label_ocr_models import (
    FigureLabelOcr,
    LabeledFigureAsset,
    ReviewedVisibleLabels,
    VisibleLabel,
    VisibleLabelProposal,
)

from .helpers import valid_asset_dict

LABEL_KINDS = (
    "latin_letter",
    "greek_letter",
    "number",
    "angle_value",
    "axis_label",
    "legend_text",
    "table_text",
    "math_symbol",
    "text",
)
MODEL_ID = "Qwen/Qwen3-VL-8B-Instruct"
PROMPT_VERSION = "figure-b3-v1"


def make_label(text: str = "A", kind: str = "latin_letter") -> VisibleLabel:
    return VisibleLabel(text=text, kind=kind)


def make_proposal(
    *,
    labels: list[VisibleLabel] | None = None,
    confidence: float = 0.94,
    needs_review: bool = True,
    prompt_version: str = PROMPT_VERSION,
) -> VisibleLabelProposal:
    return VisibleLabelProposal(
        labels=[make_label(), make_label("β", "greek_letter")] if labels is None else labels,
        confidence=confidence,
        needs_review=needs_review,
        model_id=MODEL_ID,
        quantization="4-bit",
        prompt_version=prompt_version,
    )


def make_reviewed(
    *,
    labels: list[VisibleLabel] | None = None,
    status: str = "approved",
) -> ReviewedVisibleLabels:
    return ReviewedVisibleLabels(
        labels=[make_label(), make_label("β", "greek_letter")] if labels is None else labels,
        status=status,
        reviewer="human-b3",
        source_proposal_id="hk-dse-2015-math-p2-q018-fig01:figure-b3-v1",
    )


def failed_audit() -> dict[str, object]:
    return {
        "error": "response is not valid JSON",
        "response_path": "label_ocr_response.txt",
        "response_sha256": "d" * 64,
        "model_id": MODEL_ID,
        "quantization": "4-bit",
        "prompt_version": PROMPT_VERSION,
    }


def make_b2_asset() -> ClassifiedFigureAsset:
    classification_proposal = {
        "visual_family": "geometry",
        "subtype": "triangle",
        "secondary_tags": [],
        "confidence": 0.91,
        "evidence": ["Three visible straight edges form a triangle"],
        "needs_review": True,
        "model_id": MODEL_ID,
        "quantization": "4-bit",
        "prompt_version": "figure-b2-v1",
    }
    classification_review = {
        "visual_family": "geometry",
        "subtype": "triangle",
        "secondary_tags": [],
        "status": "approved",
        "reviewer": "human-b2",
        "source_proposal_id": "hk-dse-2015-math-p2-q018-fig01:figure-b2-v1",
    }
    return ClassifiedFigureAsset.model_validate(
        valid_asset_dict(
            schema_version="1.1",
            pipeline_version="figure-b2-v1",
            figure_type="geometry",
            classification={
                "proposed": classification_proposal,
                "reviewed": classification_review,
                "status": "approved",
            },
        )
    )


def make_labeled_asset(
    label_ocr: FigureLabelOcr,
    *,
    visible_labels: list[VisibleLabel] | None = None,
) -> LabeledFigureAsset:
    b2 = make_b2_asset()
    payload = b2.model_dump(mode="json")
    payload.update(
        {
            "schema_version": "1.2",
            "pipeline_version": "figure-b3-v1",
            "visible_labels": [
                label.model_dump(mode="json")
                for label in (visible_labels or [])
            ],
            "label_ocr": label_ocr.model_dump(mode="json"),
        }
    )
    return LabeledFigureAsset.model_validate(payload)


def test_visible_label_strips_text_and_accepts_every_contract_kind() -> None:
    assert make_label("  β  ", "greek_letter").text == "β"

    for kind in LABEL_KINDS:
        assert make_label("x", kind).kind == kind


@pytest.mark.parametrize("text", ["", "   ", "A\nB", "A\rB"])
def test_visible_label_rejects_blank_or_newline_text(text: str) -> None:
    with pytest.raises(ValidationError):
        make_label(text)


def test_visible_label_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        make_label("A", "unknown_kind")


def test_visible_label_proposal_allows_empty_labels_and_enforces_limit() -> None:
    assert make_proposal(labels=[]).labels == []

    with pytest.raises(ValidationError):
        make_proposal(labels=[make_label()] * 65)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_visible_label_proposal_rejects_out_of_range_confidence(
    confidence: float,
) -> None:
    with pytest.raises(ValidationError):
        make_proposal(confidence=confidence)


def test_visible_label_proposal_requires_review_and_runtime_metadata() -> None:
    proposal = make_proposal()
    assert proposal.model_id == MODEL_ID
    assert proposal.quantization == "4-bit"
    assert proposal.prompt_version == PROMPT_VERSION

    with pytest.raises(ValidationError):
        make_proposal(needs_review=False)
    with pytest.raises(ValidationError):
        VisibleLabelProposal(
            labels=[],
            confidence=0.9,
            needs_review=True,
            model_id=MODEL_ID,
            quantization="8-bit",
            prompt_version=PROMPT_VERSION,
        )
    with pytest.raises(ValidationError):
        VisibleLabelProposal(
            labels=[],
            confidence=0.9,
            needs_review=True,
            model_id=MODEL_ID,
            quantization="4-bit",
            prompt_version="figure-b2-v1",
        )


@pytest.mark.parametrize(
    "prompt_version",
    ["figure-b3-v1", "figure-b3-v2", "figure-b3-v3"],
)
def test_visible_label_proposal_accepts_b3_prompt_versions(
    prompt_version: str,
) -> None:
    proposal = make_proposal(prompt_version=prompt_version)

    assert proposal.prompt_version == prompt_version


def test_visible_label_proposal_rejects_unknown_b3_prompt_version() -> None:
    with pytest.raises(ValidationError):
        make_proposal(prompt_version="figure-b3-v4")


def test_pending_ocr_requires_proposal_and_no_reviewed_record() -> None:
    proposal = make_proposal()

    pending = FigureLabelOcr(proposed=proposal, reviewed=None, status="pending")
    assert pending.proposed == proposal

    with pytest.raises(ValidationError):
        FigureLabelOcr(proposed=None, reviewed=None, status="pending")
    with pytest.raises(ValidationError):
        FigureLabelOcr(
            proposed=proposal,
            reviewed=make_reviewed(status="approved"),
            status="pending",
        )


def test_approved_ocr_requires_proposal_and_matching_review_status() -> None:
    proposal = make_proposal()
    approved = FigureLabelOcr(
        proposed=proposal,
        reviewed=make_reviewed(status="approved"),
        status="approved",
    )
    assert approved.reviewed is not None
    assert approved.reviewed.status == "approved"

    with pytest.raises(ValidationError):
        FigureLabelOcr(
            proposed=None,
            reviewed=make_reviewed(status="approved"),
            status="approved",
        )
    with pytest.raises(ValidationError):
        FigureLabelOcr(
            proposed=proposal,
            reviewed=make_reviewed(status="corrected"),
            status="approved",
        )


@pytest.mark.parametrize("status", ["corrected", "rejected"])
def test_proposalless_corrected_or_rejected_ocr_requires_failed_audit_metadata(
    status: str,
) -> None:
    labels = [] if status == "rejected" else [make_label("C")]
    reviewed = make_reviewed(labels=labels, status=status)
    audited = FigureLabelOcr(
        proposed=None,
        reviewed=reviewed,
        status=status,
        **failed_audit(),
    )
    assert audited.proposed is None
    assert audited.reviewed == reviewed
    assert audited.response_path == "label_ocr_response.txt"

    with pytest.raises(ValidationError):
        FigureLabelOcr(proposed=None, reviewed=reviewed, status=status)


def test_rejected_review_requires_empty_labels() -> None:
    with pytest.raises(ValidationError):
        make_reviewed(labels=[make_label()], status="rejected")

    assert make_reviewed(labels=[], status="rejected").labels == []


@pytest.mark.parametrize(
    ("status", "label_ocr", "visible_labels"),
    [
        (
            "pending",
            FigureLabelOcr(proposed=make_proposal(), reviewed=None, status="pending"),
            [],
        ),
        (
            "failed",
            FigureLabelOcr(proposed=None, reviewed=None, status="failed", **failed_audit()),
            [],
        ),
        (
            "rejected",
            FigureLabelOcr(
                proposed=make_proposal(),
                reviewed=make_reviewed(labels=[], status="rejected"),
                status="rejected",
            ),
            [],
        ),
        (
            "approved",
            FigureLabelOcr(
                proposed=make_proposal(),
                reviewed=make_reviewed(labels=[make_label("A")], status="approved"),
                status="approved",
            ),
            [make_label("A")],
        ),
        (
            "corrected",
            FigureLabelOcr(
                proposed=None,
                reviewed=make_reviewed(labels=[make_label("C")], status="corrected"),
                status="corrected",
                **failed_audit(),
            ),
            [make_label("C")],
        ),
    ],
)
def test_labeled_asset_visible_labels_follow_ocr_status(
    status: str,
    label_ocr: FigureLabelOcr,
    visible_labels: list[VisibleLabel],
) -> None:
    asset = make_labeled_asset(label_ocr, visible_labels=visible_labels)
    assert asset.label_ocr.status == status
    assert asset.visible_labels == visible_labels

    b2 = make_b2_asset()
    assert asset.classification == b2.classification
    assert asset.source == b2.source
    assert asset.figure_type == b2.figure_type


@pytest.mark.parametrize("status", ["pending", "failed", "rejected"])
def test_labeled_asset_rejects_visible_labels_before_acceptance(status: str) -> None:
    if status == "pending":
        label_ocr = FigureLabelOcr(proposed=make_proposal(), reviewed=None, status=status)
    elif status == "failed":
        label_ocr = FigureLabelOcr(proposed=None, reviewed=None, status=status, **failed_audit())
    else:
        label_ocr = FigureLabelOcr(
            proposed=make_proposal(),
            reviewed=make_reviewed(labels=[], status=status),
            status=status,
        )

    with pytest.raises(ValidationError):
        make_labeled_asset(label_ocr, visible_labels=[make_label("A")])


def test_labeled_asset_requires_reviewed_labels_for_accepted_status() -> None:
    label_ocr = FigureLabelOcr(
        proposed=make_proposal(),
        reviewed=make_reviewed(labels=[make_label("A")], status="approved"),
        status="approved",
    )

    with pytest.raises(ValidationError):
        make_labeled_asset(label_ocr, visible_labels=[make_label("B")])
