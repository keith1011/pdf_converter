from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ocr_pipeline.models import LayoutBlock


class EngineError(RuntimeError):
    """Missing dependency / weights / hard engine failure (fail loud)."""


@runtime_checkable
class LayoutEngine(Protocol):
    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]: ...

    def release(self) -> None: ...


@runtime_checkable
class TextEngine(Protocol):
    def ocr(self, crop_path: Path) -> str: ...


@runtime_checkable
class FormulaEngine(Protocol):
    def ocr(self, crop_path: Path) -> str: ...
