"""Stage1 adapter for the locked DSE Mathematics CP Paper 2 regioner."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from .dse_mcq_layout import regions_to_layout_blocks
from .dse_mcq_ocr import read_rapidocr_lines
from .dse_mcq_profile import McqProfile
from .dse_mcq_region import detect_mcq_regions
from .dse_mcq_types import McqRegion, OcrLine
from .models import LayoutBlock

logger = logging.getLogger(__name__)

LineReader = Callable[[Path], list[OcrLine]]
RegionDetector = Callable[[list[OcrLine], McqProfile], list[McqRegion]]


class DseMcqLayoutEngine:
    """Produce one question crop per DSE MCQ, with generic fallback per page."""

    def __init__(
        self,
        *,
        profile: McqProfile,
        fallback_engine: object,
        line_reader: LineReader = read_rapidocr_lines,
        region_detector: RegionDetector = detect_mcq_regions,
        skip_first_page: bool = True,
    ) -> None:
        self.profile = profile
        self.fallback_engine = fallback_engine
        self.line_reader = line_reader
        self.region_detector = region_detector
        self.skip_first_page = skip_first_page

    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]:
        if self.skip_first_page and page == 1:
            logger.info("DSE MCQ: skipping candidate-instructions page 1")
            return []

        try:
            regions = self.region_detector(self.line_reader(image_path), self.profile)
        except Exception as exc:
            logger.warning("DSE MCQ layout failed on page %s: %s; using generic layout", page, exc)
            return self.fallback_engine.analyze(image_path, page)

        if not regions:
            logger.warning("DSE MCQ: no question regions on page %s; using generic layout", page)
            return self.fallback_engine.analyze(image_path, page)

        return regions_to_layout_blocks(
            image_path,
            regions,
            page=page,
            profile_id=self.profile.id,
            crops_dir=image_path.parent / "crops",
        )

    def release(self) -> None:
        self.fallback_engine.release()
