"""Types for DSE Paper2 MCQ question-region detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LineKind(str, Enum):
    OTHER = "other"
    STEM_CANDIDATE = "stem_candidate"
    OPTION_A = "option_a"
    OPTION_B = "option_b"
    OPTION_C = "option_c"
    OPTION_D = "option_d"


@dataclass(frozen=True)
class OcrLine:
    text: str
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    page_width: float
    page_height: float


@dataclass
class TaggedLine:
    line: OcrLine
    kind: LineKind
    question_id: int | None = None


@dataclass
class McqAnchors:
    A: bool = False
    B: bool = False
    C: bool = False
    D: bool = False

    @property
    def hit_count(self) -> int:
        return int(self.A) + int(self.B) + int(self.C) + int(self.D)

    def as_dict(self) -> dict[str, bool]:
        return {"A": self.A, "B": self.B, "C": self.C, "D": self.D}


@dataclass
class McqRegion:
    question_id: int
    bbox: tuple[float, float, float, float]
    anchors: McqAnchors
    incomplete: bool
    line_indices: list[int] = field(default_factory=list)
    orphan: bool = False
