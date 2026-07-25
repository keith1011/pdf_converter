"""N-up layout types for pre-MinerU classifier + crop gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class NupClass(str, Enum):
    ONE = "1"
    TWO_LR = "2_lr"
    FOUR_2X2 = "4_2x2"
    UNCERTAIN = "uncertain"


@dataclass
class NupPanel:
    version_id: str
    bbox_norm: tuple[float, float, float, float]  # x1,y1,x2,y2 in [0,1]
    path: Path | None = None
    semantic: str | None = None


@dataclass
class NupDecision:
    page_index: int
    nup_class: NupClass
    confidence: float
    threshold: float
    fallback: bool
    panels: list[NupPanel] = field(default_factory=list)
