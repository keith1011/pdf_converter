from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

BBox = tuple[StrictInt, StrictInt, StrictInt, StrictInt]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DOCUMENT_ID_RE = re.compile(r"^hk-dse-\d{4}-math-p2$")
_QUESTION_ID_RE = re.compile(r"^hk-dse-\d{4}-math-p2-q\d{3}$")
_ASSET_ID_RE = re.compile(r"^hk-dse-\d{4}-math-p2-q\d{3}-fig\d{2}$")


def _valid_bbox(value: BBox) -> BBox:
    x1, y1, x2, y2 = value
    if min(value) < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError("bbox must be non-negative and non-empty")
    return value


def _valid_sha256(value: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
    return value


def _valid_relative_path(value: str) -> str:
    path = PurePosixPath(value.replace(chr(92), "/"))
    windows_path = PureWindowsPath(value)
    if (
        path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or windows_path.root
        or ".." in path.parts
        or str(path) in {"", "."}
    ):
        raise ValueError("path must be a non-empty safe relative path")
    return path.as_posix()


def resolve_bundle_path(root: Path, relative_path: str) -> Path:
    safe_relative_path = _valid_relative_path(relative_path)
    resolved_root = root.resolve()
    resolved_path = (resolved_root / safe_relative_path).resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("bundle path resolves outside its bundle") from exc
    return resolved_path


def _valid_source_reference(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        raise ValueError("source reference cannot be empty")
    return normalized


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetValidation(StrictModel):
    status: Literal["pending"] = "pending"
    reviewed: Literal[False] = False


class AssetProvenance(StrictModel):
    method: Literal["mineru_confirmed", "manual"]
    detector: str | None = None
    detector_label: str | None = None
    candidate_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_method_fields(self) -> AssetProvenance:
        if self.method == "manual":
            if any(
                value is not None
                for value in (
                    self.detector,
                    self.detector_label,
                    self.candidate_index,
                )
            ):
                raise ValueError("manual provenance cannot contain detector fields")
        elif not self.detector or not self.detector_label:
            raise ValueError("confirmed MinerU provenance requires detector fields")
        elif self.candidate_index is None:
            raise ValueError("confirmed MinerU provenance requires candidate_index")
        return self


class AssetSource(StrictModel):
    source_pdf: str
    page: int = Field(ge=1)
    original_question_crop_path: str
    question_crop_path: str
    question_crop_sha256: str
    question_bbox: BBox
    question_bbox_space: Literal["page_pixels"] = "page_pixels"
    crop_path: str
    bbox: BBox
    bbox_space: Literal["question_crop_pixels"] = "question_crop_pixels"
    sha256: str

    _validate_question_bbox = field_validator("question_bbox")(_valid_bbox)
    _validate_bbox = field_validator("bbox")(_valid_bbox)
    _validate_question_hash = field_validator("question_crop_sha256")(_valid_sha256)
    _validate_crop_hash = field_validator("sha256")(_valid_sha256)
    _validate_source_references = field_validator("source_pdf", "original_question_crop_path")(
        _valid_source_reference
    )
    _validate_bundle_paths = field_validator("question_crop_path", "crop_path")(
        _valid_relative_path
    )


class FigureProposal(StrictModel):
    bbox: BBox
    bbox_space: Literal["question_crop_pixels"] = "question_crop_pixels"
    label: str = Field(min_length=1)
    detector: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    _validate_bbox = field_validator("bbox")(_valid_bbox)


class ProposalBundle(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    document_id: str
    parent_question_id: str
    page: int = Field(ge=1)
    question_id: int = Field(ge=1)
    question_crop_path: str
    question_crop_sha256: str
    question_crop_width: int = Field(gt=0)
    question_crop_height: int = Field(gt=0)
    proposals: list[FigureProposal]

    _validate_question_hash = field_validator("question_crop_sha256")(_valid_sha256)
    _validate_question_path = field_validator("question_crop_path")(_valid_source_reference)


class FigureAsset(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    pipeline_version: Literal["figure-b1-v1"] = "figure-b1-v1"
    document_id: str
    asset_id: str
    parent_question_id: str
    asset_type: Literal["figure"] = "figure"
    figure_type: Literal["unknown"] = "unknown"
    source: AssetSource
    provenance: AssetProvenance
    visible_labels: list[object] = Field(default_factory=list, max_length=0)
    description: None = None
    entities: list[object] = Field(default_factory=list, max_length=0)
    relations: list[object] = Field(default_factory=list, max_length=0)
    validation: AssetValidation = Field(default_factory=AssetValidation)

    @model_validator(mode="after")
    def validate_identity(self) -> FigureAsset:
        if not _DOCUMENT_ID_RE.fullmatch(self.document_id):
            raise ValueError("invalid document_id")
        if not _QUESTION_ID_RE.fullmatch(self.parent_question_id):
            raise ValueError("invalid parent_question_id")
        if not _ASSET_ID_RE.fullmatch(self.asset_id):
            raise ValueError("invalid asset_id")
        if not self.parent_question_id.startswith(self.document_id + "-q"):
            raise ValueError("question ID does not belong to document")
        if not self.asset_id.startswith(self.parent_question_id + "-fig"):
            raise ValueError("asset ID does not belong to parent question")
        return self
