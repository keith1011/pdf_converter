from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from .models import FigureAsset, StrictModel, _valid_relative_path

VisualFamily = Literal[
    "geometry",
    "coordinate_graph",
    "function_graph",
    "statistical_chart",
    "table",
    "physical_diagram",
    "illustration",
    "unknown",
]

EvidenceItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_RESPONSE_SHA256_PATTERN = r"^[0-9a-f]{64}$"

SUBTYPE_BY_FAMILY: dict[str, frozenset[str]] = {
    "geometry": frozenset(
        {
            "triangle",
            "quadrilateral",
            "circle",
            "polygon",
            "solid",
            "angle",
            "transformation",
            "other",
        }
    ),
    "coordinate_graph": frozenset({"point_plot", "line_segment", "locus", "vector", "other"}),
    "function_graph": frozenset(
        {
            "linear",
            "quadratic",
            "polynomial",
            "piecewise",
            "trigonometric",
            "exponential",
            "other",
        }
    ),
    "statistical_chart": frozenset({"bar", "line", "pie", "scatter", "box", "histogram", "other"}),
    "table": frozenset({"data_table", "frequency_table", "value_table", "other"}),
    "physical_diagram": frozenset(
        {"flowchart", "circuit", "mechanical", "engineering", "chemistry", "other"}
    ),
    "illustration": frozenset({"map", "photo", "decorative", "other"}),
    "unknown": frozenset({"unclassified"}),
}


class ClassificationProposal(StrictModel):
    visual_family: VisualFamily
    subtype: str = Field(min_length=1)
    secondary_tags: list[VisualFamily] = Field(default_factory=list, max_length=3)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=3)
    needs_review: Literal[True] = True
    model_id: str = Field(min_length=1)
    quantization: Literal["4-bit"] = "4-bit"
    prompt_version: Literal["figure-b2-v1"] = "figure-b2-v1"

    @model_validator(mode="after")
    def validate_taxonomy(self) -> ClassificationProposal:
        allowed_subtypes = SUBTYPE_BY_FAMILY[self.visual_family]
        if self.subtype not in allowed_subtypes:
            raise ValueError(f"subtype {self.subtype!r} is not valid for {self.visual_family!r}")
        if len(set(self.secondary_tags)) != len(self.secondary_tags):
            raise ValueError("secondary_tags must be unique")
        if "unknown" in self.secondary_tags:
            raise ValueError("unknown cannot be a secondary tag")
        if self.visual_family in self.secondary_tags:
            raise ValueError("primary visual_family cannot repeat in secondary_tags")
        return self


class ReviewedClassification(StrictModel):
    visual_family: VisualFamily
    subtype: str = Field(min_length=1)
    secondary_tags: list[VisualFamily] = Field(default_factory=list, max_length=3)
    status: Literal["approved", "corrected", "rejected"]
    reviewer: str = Field(min_length=1)
    source_proposal_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_review(self) -> ReviewedClassification:
        allowed_subtypes = SUBTYPE_BY_FAMILY[self.visual_family]
        if self.subtype not in allowed_subtypes:
            raise ValueError("review subtype is incompatible with visual_family")
        if len(set(self.secondary_tags)) != len(self.secondary_tags):
            raise ValueError("secondary_tags must be unique")
        if "unknown" in self.secondary_tags or self.visual_family in self.secondary_tags:
            raise ValueError("review secondary_tags contains an invalid family")
        if self.status == "rejected" and self.visual_family != "unknown":
            raise ValueError("rejected reviews must use visual_family=unknown")
        if self.status != "rejected" and self.visual_family == "unknown":
            raise ValueError("approved/corrected reviews cannot use unknown")
        return self


class FigureClassification(StrictModel):
    proposed: ClassificationProposal | None = None
    reviewed: ReviewedClassification | None = None
    status: Literal["pending", "approved", "corrected", "rejected", "failed"] = "pending"
    response_path: str | None = Field(default=None, min_length=1)
    response_sha256: str | None = Field(
        default=None,
        pattern=_RESPONSE_SHA256_PATTERN,
    )
    error: str | None = None
    model_id: str | None = Field(default=None, min_length=1)
    quantization: Literal["4-bit"] | None = None
    prompt_version: Literal["figure-b2-v1"] | None = None

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
    def validate_state(self) -> FigureClassification:
        if self.status == "pending":
            if self.proposed is None:
                raise ValueError("pending classification requires a proposal")
            if self.reviewed is not None:
                raise ValueError("pending classification cannot have reviewed data")
        elif self.status in {"approved", "corrected", "rejected"}:
            if self.proposed is None and self.status == "approved":
                raise ValueError("approved classification requires a proposal")
            if self.reviewed is None or self.reviewed.status != self.status:
                raise ValueError("reviewed status must match classification status")
        else:
            if self.proposed is not None or self.reviewed is not None:
                raise ValueError("failed classification cannot contain proposal or review data")
            if self.error is None or not self.error.strip():
                raise ValueError("failed classification requires an error")
        response_reference = (self.response_path, self.response_sha256)
        if (self.response_path is None) != (self.response_sha256 is None):
            raise ValueError("response_path and response_sha256 must be provided together")

        failure_metadata = (self.model_id, self.quantization, self.prompt_version)
        if self.status == "failed":
            if any(value is None for value in response_reference):
                raise ValueError("failed classification requires a raw response reference")
            if any(value is None for value in failure_metadata):
                raise ValueError("failed classification requires model metadata")
        elif self.proposed is None:
            if self.status not in {"corrected", "rejected"}:
                raise ValueError("proposal-less review must be corrected or rejected")
            if self.error is None or not self.error.strip():
                raise ValueError("failed-source review requires the failure audit error")
            if any(value is None for value in response_reference):
                raise ValueError("failed-source review requires a raw response reference")
            if any(value is None for value in failure_metadata):
                raise ValueError("failed-source review requires model metadata")
        elif self.error is not None or any(value is not None for value in failure_metadata):
            raise ValueError(
                "error and top-level model metadata are only valid for failed-source reviews"
            )
        return self


class ClassifiedFigureAsset(FigureAsset):
    schema_version: Literal["1.1"] = "1.1"
    pipeline_version: Literal["figure-b2-v1"] = "figure-b2-v1"
    figure_type: VisualFamily = "unknown"
    classification: FigureClassification

    @model_validator(mode="after")
    def validate_figure_type(self) -> ClassifiedFigureAsset:
        if (
            self.classification.status in {"pending", "failed", "rejected"}
            and self.figure_type != "unknown"
        ):
            raise ValueError("unresolved classification must keep figure_type=unknown")
        if self.classification.status in {"approved", "corrected"}:
            reviewed = self.classification.reviewed
            if reviewed is None or self.figure_type != reviewed.visual_family:
                raise ValueError("figure_type must match the reviewed visual_family")
        return self

    @classmethod
    def from_b1(
        cls,
        asset: FigureAsset,
        classification: FigureClassification,
        *,
        figure_type: VisualFamily = "unknown",
    ) -> ClassifiedFigureAsset:
        payload = asset.model_dump(mode="json")
        payload.update(
            {
                "schema_version": "1.1",
                "pipeline_version": "figure-b2-v1",
                "figure_type": figure_type,
                "classification": classification.model_dump(mode="json"),
            }
        )
        return cls.model_validate(payload)
