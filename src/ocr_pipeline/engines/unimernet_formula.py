"""UniMERNet formula adapter via MinerU, with no VLM fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import EngineError


def _load_unimernet_model(*, device: str) -> Any:
    """Load UniMERNet only when a formula crop is first requested."""
    try:
        import os

        from mineru.model.mfr.unimernet.Unimernet import UnimernetModel
        from mineru.utils.enum_class import ModelPath
        from mineru.utils.models_download_utils import (
            auto_download_and_get_model_root_path,
        )
    except ImportError as exc:
        raise EngineError(
            "UniMERNet requires MinerU. Install it with "
            "`pip install -r requirements-mineru-ppocr.txt`."
        ) from exc
    try:
        weight_dir = os.path.join(
            auto_download_and_get_model_root_path(ModelPath.unimernet_small),
            ModelPath.unimernet_small,
        )
        return UnimernetModel(weight_dir, device)
    except Exception as exc:
        raise EngineError(
            "UniMERNet could not load weights. Ensure the MinerU formula model "
            "is available locally before running this experiment."
        ) from exc


class UnimernetFormulaEngine:
    """Transcribe a formula crop using MinerU's UniMERNet implementation."""

    def __init__(self, *, device: str = "cuda") -> None:
        self.device = device
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = _load_unimernet_model(device=self.device)
        return self._model

    def ocr(self, crop_path: Path) -> str:
        try:
            import cv2

            image = cv2.imread(str(crop_path))
            if image is None:
                raise ValueError("could not read formula crop")
            height, width = image.shape[:2]
            results = self._ensure_model().predict(
                [
                    {
                        "label": "display_formula",
                        "bbox": [0, 0, width, height],
                    }
                ],
                image,
            )
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"UniMERNet inference failed for {crop_path}.") from exc
        if not results:
            return ""
        result = results[0].get("latex", "") if isinstance(results[0], dict) else ""
        return str(result).strip()
