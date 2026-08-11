from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .classification_models import ClassifiedFigureAsset
from .models import StrictModel, _valid_relative_path

VisibleLabelKind = Literal[
    "latin_letter",
    "greek_letter",
    "number",
    "angle_value",
    "axis_label",
    "legend_text",
    "table_text",
    "math_symbol",
    "text",
]
VisibleLabelPromptVersion = Literal[
    "figure-b3-v1",
    "figure-b3-v2",
    "figure-b3-v3",
]

_RESPONSE_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class VisibleLabel(StrictModel):
    text: str = Field(min_length=1, max_length=128)
    kind: VisibleLabelKind

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("visible label text cannot be blank")
        if any(character in normalized for character in ("\r", "\n")):
            raise ValueError("visible label text must be one line")
        return normalized


class VisibleLabelProposal(StrictModel):
    labels: list[VisibleLabel] = Field(default_factory=list, max_length=64)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: Literal[True] = True
    model_id: str = Field(min_length=1)
    quantization: Literal["4-bit"] = "4-bit"
    prompt_version: VisibleLabelPromptVersion = "figure-b3-v3"


class ReviewedVisibleLabels(StrictModel):
    labels: list[VisibleLabel] = Field(default_factory=list, max_length=64)
    status: Literal["approved", "corrected", "rejected"]
    reviewer: str = Field(min_length=1)
    source_proposal_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_review(self) -> ReviewedVisibleLabels:
        if self.status == "rejected" and self.labels:
            raise ValueError("rejected visible-label review must use an empty label list")
        return self


class FigureLabelOcr(StrictModel):
    proposed: VisibleLabelProposal | None = None
    reviewed: ReviewedVisibleLabels | None = None
    status: Literal["pending", "approved", "corrected", "rejected", "failed"] = "pending"
    response_path: str | None = Field(default=None, min_length=1)
    response_sha256: str | None = Field(
        default=None,
        pattern=_RESPONSE_SHA256_PATTERN,
    )
    error: str | None = None
    model_id: str | None = Field(default=None, min_length=1)
    quantization: Literal["4-bit"] | None = None
    prompt_version: VisibleLabelPromptVersion | None = None

    @field_validator("response_path")
    @classmethod
    def validate_response_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return _valid_relative_path(value)
        except ValueError as exc:
            raise ValueError("response_path must be a safe relative path") from exc

    @model_validator(mode="after")
    def validate_state(self) -> FigureLabelOcr:
        if self.status == "pending":
            if self.proposed is None:
                raise ValueError("pending label OCR requires a proposal")
            if self.reviewed is not None:
                raise ValueError("pending label OCR cannot have reviewed data")
        elif self.status in {"approved", "corrected", "rejected"}:
            if self.proposed is None and self.status == "approved":
                raise ValueError("approved label OCR requires a proposal")
            if self.reviewed is None or self.reviewed.status != self.status:
                raise ValueError("reviewed status must match label OCR status")
        else:
            if self.proposed is not None or self.reviewed is not None:
                raise ValueError("failed label OCR cannot contain proposal or review data")
            if self.error is None or not self.error.strip():
                raise ValueError("failed label OCR requires an error")

        response_reference = (self.response_path, self.response_sha256)
        if (self.response_path is None) != (self.response_sha256 is None):
            raise ValueError("response_path and response_sha256 must be provided together")

        failure_metadata = (self.model_id, self.quantization, self.prompt_version)
        if self.status == "failed":
            if any(value is None for value in response_reference):
                raise ValueError("failed label OCR requires a raw response reference")
            if any(value is None for value in failure_metadata):
                raise ValueError("failed label OCR requires model metadata")
        elif self.proposed is None:
            if self.status not in {"corrected", "rejected"}:
                raise ValueError("proposal-less label review must be corrected or rejected")
            if self.error is None or not self.error.strip():
                raise ValueError("failed-source review requires the label OCR error")
            if any(value is None for value in response_reference):
                raise ValueError("failed-source review requires a raw response reference")
            if any(value is None for value in failure_metadata):
                raise ValueError("failed-source review requires model metadata")
        elif self.error is not None or any(value is not None for value in failure_metadata):
            raise ValueError(
                "error and top-level model metadata are only valid for failed-source reviews"
            )
        return self


class LabeledFigureAsset(ClassifiedFigureAsset):
    schema_version: Literal["1.2"] = "1.2"
    pipeline_version: Literal["figure-b3-v1"] = "figure-b3-v1"
    visible_labels: list[VisibleLabel] = Field(default_factory=list, max_length=64)
    label_ocr: FigureLabelOcr

    @model_validator(mode="after")
    def validate_visible_labels(self) -> LabeledFigureAsset:
        status = self.label_ocr.status
        if status in {"pending", "failed", "rejected"} and self.visible_labels:
            raise ValueError("unresolved label OCR must keep visible_labels empty")
        if status in {"approved", "corrected"}:
            reviewed = self.label_ocr.reviewed
            if reviewed is None or self.visible_labels != reviewed.labels:
                raise ValueError("visible_labels must match the reviewed label list")
        return self

    @classmethod
    def from_b2(
        cls,
        asset: ClassifiedFigureAsset,
        label_ocr: FigureLabelOcr,
        *,
        visible_labels: list[VisibleLabel] | None = None,
    ) -> LabeledFigureAsset:
        payload = asset.model_dump(mode="json")
        payload.update(
            {
                "schema_version": "1.2",
                "pipeline_version": "figure-b3-v1",
                "visible_labels": [
                    label.model_dump(mode="json") for label in (visible_labels or [])
                ],
                "label_ocr": label_ocr.model_dump(mode="json"),
            }
        )
        return cls.model_validate(payload)
