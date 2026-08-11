from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image

from figure_pipeline.models import FigureProposal
from ocr_pipeline.engines.mineru_layout import MineruLayoutEngine
from ocr_pipeline.models import BlockType


class MineruFigureDetector:
    name = "mineru_pp_doclayout_v2"

    def __init__(self, *, engine: Any | None = None, device: str = "cuda") -> None:
        self.engine = engine or MineruLayoutEngine(device=device)

    def detect(self, question_crop: Path, *, page: int) -> list[FigureProposal]:
        with Image.open(question_crop) as image:
            width, height = image.size

        proposals: list[FigureProposal] = []
        for block in self.engine.analyze(question_crop, page=page):
            if block.block_type is not BlockType.FIGURE:
                continue
            bbox = (
                math.floor(block.bbox.x1),
                math.floor(block.bbox.y1),
                math.ceil(block.bbox.x2),
                math.ceil(block.bbox.y2),
            )
            x1, y1, x2, y2 = bbox
            if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
                continue
            if x2 <= x1 or y2 <= y1:
                continue
            proposals.append(
                FigureProposal(
                    bbox=bbox,
                    label=str(block.meta.get("label") or "figure"),
                    detector=self.name,
                )
            )
        return proposals
