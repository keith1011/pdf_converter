"""Shared data models for the OCR pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class BlockType(str, Enum):
    TEXT = "text"
    TITLE = "title"
    LIST = "list"
    FORMULA = "formula"
    EQUATION = "equation"
    TABLE = "table"
    FIGURE = "figure"
    OTHER = "other"


@dataclass
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def as_int_tuple(self) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = map(int, (self.x1, self.y1, self.x2, self.y2))
        if x2 <= x1:
            x2 = x1 + 1
        if y2 <= y1:
            y2 = y1 + 1
        return x1, y1, x2, y2

    def clamp(self, width: int, height: int) -> BBox:
        return BBox(
            x1=max(0, min(self.x1, width - 1)),
            y1=max(0, min(self.y1, height - 1)),
            x2=max(1, min(self.x2, width)),
            y2=max(1, min(self.y2, height)),
        )


@dataclass
class LayoutBlock:
    block_id: str
    block_type: BlockType
    bbox: BBox
    order: int
    page: int
    image_path: Path
    crop_path: Path | None = None
    raw_text: str = ""
    latex: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class PageResult:
    page: int
    image_path: Path
    blocks: list[LayoutBlock]
    draft: str = ""
    txt: str = ""
    tex: str = ""


@dataclass
class PipelineResult:
    source: str
    pages: list[PageResult]
    draft: str = ""
    txt: str = ""
    tex: str = ""
    txt_path: Path | None = None
    tex_path: Path | None = None
    pageir_path: Path | None = None
    warnings: list[str] = field(default_factory=list)


class SegmentKind(str, Enum):
    PROSE = "prose"
    MATH = "math"
    MARK_NOTE = "mark_note"


class IntegrityStatus(str, Enum):
    OK = "ok"
    REPAIRED = "repaired"
    FAIL = "fail"


@dataclass
class ContentSegment:
    """One linear content unit for content-first Ship 1."""

    kind: SegmentKind
    text: str
    source_block_id: str
    bbox: BBox
    integrity: IntegrityStatus = IntegrityStatus.OK


@dataclass
class PageIR:
    """Per-page intermediate representation (ordered segments)."""

    page_index: int
    segments: list[ContentSegment] = field(default_factory=list)
