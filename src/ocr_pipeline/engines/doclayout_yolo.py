"""DocLayout-YOLO layout adapter with explicit dependency and weight failures."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ocr_pipeline.models import BBox, BlockType, LayoutBlock

from .base import EngineError

DEFAULT_MODEL_ID = "juliozhao/DocLayout-YOLO-DocStructBench"

_LABEL_MAP = {
    "formula": BlockType.FORMULA,
    "isolateformula": BlockType.FORMULA,
    "equation": BlockType.EQUATION,
    "inlineformula": BlockType.EQUATION,
    "title": BlockType.TITLE,
    "sectionheader": BlockType.TITLE,
    "table": BlockType.TABLE,
    "plaintext": BlockType.TEXT,
    "text": BlockType.TEXT,
}


def map_doclayout_label(label: str | None) -> BlockType:
    """Convert a DocLayout class name to the pipeline's common block type."""
    key = re.sub(r"[^a-z]", "", (label or "").lower())
    return _LABEL_MAP.get(key, BlockType.OTHER)


def _load_doclayout_model(*, model_id: str) -> Any:
    """Load DocLayout-YOLO only when the first page is analyzed."""
    try:
        from doclayout_yolo import YOLOv10
    except ImportError as exc:
        raise EngineError(
            "DocLayout-YOLO requires doclayout-yolo. Install it with "
            "`pip install -r requirements-got-ppocr.txt`."
        ) from exc
    try:
        return YOLOv10.from_pretrained(model_id)
    except Exception as exc:
        raise EngineError(
            f"DocLayout-YOLO could not load weights {model_id!r}. "
            "Ensure the model is available locally or Hugging Face access works."
        ) from exc


class DocLayoutYoloEngine:
    """Detect document blocks using DocLayout-YOLO."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_MODEL_ID,
        imgsz: int = 1024,
        conf: float = 0.2,
        device: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.imgsz = imgsz
        self.conf = conf
        self.device = device
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = _load_doclayout_model(model_id=self.model_id)
        return self._model

    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]:
        kwargs: dict[str, Any] = {"imgsz": self.imgsz, "conf": self.conf}
        if self.device:
            kwargs["device"] = self.device
        try:
            results = self._ensure_model().predict(str(image_path), **kwargs)
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"DocLayout-YOLO inference failed for {image_path}.") from exc

        blocks: list[LayoutBlock] = []
        for result in results:
            names = getattr(result, "names", {})
            for box in getattr(result, "boxes", None) or []:
                coords = box.xyxy.squeeze().tolist()
                if len(coords) != 4:
                    continue
                class_id = int(box.cls)
                label = str(names.get(class_id, class_id)) if hasattr(names, "get") else str(names[class_id])
                blocks.append(
                    LayoutBlock(
                        block_id=f"p{page:03d}_b{len(blocks):03d}",
                        block_type=map_doclayout_label(label),
                        bbox=BBox(*(float(value) for value in coords)),
                        order=len(blocks),
                        page=page,
                        image_path=image_path,
                        meta={"label": label, "confidence": float(box.conf)},
                    )
                )
        blocks.sort(key=lambda block: (block.bbox.y1, block.bbox.x1, block.order))
        for order, block in enumerate(blocks):
            block.order = order
        return blocks

    def release(self) -> None:
        self._model = None
