from __future__ import annotations

from pathlib import Path
from typing import Protocol

from figure_pipeline.models import FigureProposal


class FigureDetector(Protocol):
    def detect(self, question_crop: Path, *, page: int) -> list[FigureProposal]: ...
