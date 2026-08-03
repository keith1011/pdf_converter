"""MinerU layout adapter (PP-DocLayoutV2) with fail-loud dependency errors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.reading_order import assign_reading_order

from .base import EngineError

_LABEL_MAP = {
    "text": BlockType.TEXT,
    "plain_text": BlockType.TEXT,
    "paragraph_title": BlockType.TITLE,
    "doc_title": BlockType.TITLE,
    "title": BlockType.TITLE,
    "table": BlockType.TABLE,
    "table_caption": BlockType.OTHER,
    "inline_formula": BlockType.EQUATION,
    "display_formula": BlockType.FORMULA,
    "formula": BlockType.FORMULA,
    "equation": BlockType.EQUATION,
    "image": BlockType.FIGURE,
    "figure": BlockType.FIGURE,
    "picture": BlockType.FIGURE,
    "chart": BlockType.FIGURE,
    "diagram": BlockType.FIGURE,
    "figure_caption": BlockType.OTHER,
    "image_caption": BlockType.OTHER,
    "chart_caption": BlockType.OTHER,
}


def _block_type(label: object) -> BlockType:
    key = str(label or "").lower().replace(" ", "_")
    return _LABEL_MAP.get(key, BlockType.OTHER)


def _load_mineru_layout_model(*, device: str) -> Any:
    """Load MinerU PP-DocLayoutV2 only on first page analysis."""
    try:
        from mineru.model.layout.pp_doclayoutv2 import PPDocLayoutV2LayoutModel
        from mineru.utils.enum_class import ModelPath
        from mineru.utils.models_download_utils import (
            auto_download_and_get_model_root_path,
        )
    except ImportError as exc:
        raise EngineError(
            "MinerU layout requires the `mineru` package. Install with "
            "`uv sync --group mineru` (pins transformers<5), or use `.venv-mineru312`."
        ) from exc
    try:
        import os

        weight = os.path.join(
            auto_download_and_get_model_root_path(ModelPath.pp_doclayout_v2),
            ModelPath.pp_doclayout_v2,
        )
        return PPDocLayoutV2LayoutModel(weight, device)
    except Exception as exc:
        raise EngineError(
            "MinerU layout could not load its weights. Ensure the model files are "
            "available locally before running this experiment."
        ) from exc


class MineruLayoutEngine:
    """Detect document blocks using MinerU's PP-DocLayoutV2 model."""

    def __init__(self, *, device: str = "cuda") -> None:
        self.device = device
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = _load_mineru_layout_model(device=self.device)
        return self._model

    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]:
        try:
            from PIL import Image

            image = Image.open(image_path).convert("RGB")
            detections = self._ensure_model().predict(image)
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"MinerU layout inference failed for {image_path}.") from exc

        blocks: list[LayoutBlock] = []
        for detection in detections or []:
            if not isinstance(detection, dict):
                continue
            bbox = detection.get("bbox")
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                continue
            label = detection.get("label", detection.get("type", ""))
            blocks.append(
                LayoutBlock(
                    block_id=f"p{page:03d}_b{len(blocks):03d}",
                    block_type=_block_type(label),
                    bbox=BBox(*(float(value) for value in bbox)),
                    order=len(blocks),
                    page=page,
                    image_path=image_path,
                    meta={"label": str(label)},
                )
            )
        return assign_reading_order(blocks)

    def release(self) -> None:
        self._model = None
