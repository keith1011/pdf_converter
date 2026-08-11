"""DocLayout-YOLO layout adapter with explicit dependency and weight failures."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.reading_order import assign_reading_order

from .base import EngineError

DEFAULT_MODEL_ID = "juliozhao/DocLayout-YOLO-DocStructBench"
DEFAULT_WEIGHTS_FILE = "doclayout_yolo_docstructbench_imgsz1024.pt"

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


def _load_doclayout_model(*, model_id: str, weights_file: str = DEFAULT_WEIGHTS_FILE) -> Any:
    """Load DocLayout-YOLO only when the first page is analyzed.

    Prefer ``hf_hub_download`` + ``YOLOv10(path)`` — ``from_pretrained`` on
    current ``doclayout-yolo`` wrongly looks for a missing ``yolov10n.pt``.
    """
    try:
        from doclayout_yolo import YOLOv10
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise EngineError(
            "DocLayout-YOLO requires doclayout-yolo and huggingface_hub. Install "
            "with `uv sync --group got`."
        ) from exc
    try:
        weights_path = hf_hub_download(repo_id=model_id, filename=weights_file)
        return YOLOv10(weights_path)
    except Exception as exc:
        raise EngineError(
            f"DocLayout-YOLO could not load weights {model_id!r} "
            f"({weights_file!r}). Ensure the model is available locally or "
            "Hugging Face access works."
        ) from exc


class DocLayoutYoloEngine:
    """Detect document blocks using DocLayout-YOLO."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_MODEL_ID,
        weights_file: str = DEFAULT_WEIGHTS_FILE,
        imgsz: int = 1024,
        conf: float = 0.2,
        device: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.weights_file = weights_file
        self.imgsz = imgsz
        self.conf = conf
        self.device = device
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = _load_doclayout_model(
                model_id=self.model_id, weights_file=self.weights_file
            )
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
                label = (
                    str(names.get(class_id, class_id))
                    if hasattr(names, "get")
                    else str(names[class_id])
                )
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
        return assign_reading_order(blocks)

    def release(self) -> None:
        self._model = None
