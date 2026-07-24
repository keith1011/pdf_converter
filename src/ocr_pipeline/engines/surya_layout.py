from __future__ import annotations

from pathlib import Path

from ocr_pipeline.models import LayoutBlock


class SuryaLayoutEngine:
    def __init__(self, analyzer) -> None:
        self._analyzer = analyzer

    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]:
        return self._analyzer.analyze_page(image_path, page)

    def release(self) -> None:
        self._analyzer.release()
