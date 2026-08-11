"""Optional PaddleOCR-VL text engine hosted in an isolated runtime."""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .base import EngineError

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PYTHON = _ROOT / ".venv-paddleocr-vl" / "Scripts" / "python.exe"
_DEFAULT_WORKER = _ROOT / "scripts" / "paddleocr_vl_worker.py"


class PaddleOcrVlTextEngine:
    """Run PaddleOCR-VL-1.6 in its own CUDA/cuDNN runtime per pipeline run."""

    def __init__(
        self,
        *,
        device: str = "gpu",
        python_executable: Path = _DEFAULT_PYTHON,
        worker_path: Path = _DEFAULT_WORKER,
        process_factory: Callable[..., Any] = subprocess.Popen,
        use_layout_detection: bool = True,
        max_pixels: int | None = None,
        precision: str | None = None,
    ) -> None:
        self.device = "gpu" if device == "cuda" else device
        self.python_executable = python_executable
        self.worker_path = worker_path
        self.process_factory = process_factory
        self.use_layout_detection = use_layout_detection
        self.max_pixels = max_pixels
        self.precision = precision
        self._process: Any | None = None

    def _start(self) -> Any:
        if self._process is not None and self._process.poll() is None:
            return self._process
        if not self.python_executable.exists() or not self.worker_path.exists():
            raise EngineError(
                "PaddleOCR-VL runtime is missing. Create .venv-paddleocr-vl and install PaddleOCR-VL."
            )
        command = [str(self.python_executable), str(self.worker_path), "--device", self.device]
        if not self.use_layout_detection:
            command.append("--disable-layout-detection")
        if self.max_pixels is not None:
            command.extend(("--max-pixels", str(self.max_pixels)))
        if self.precision is not None:
            command.extend(("--precision", self.precision))
        self._process = self.process_factory(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        return self._process

    @staticmethod
    def _read_response(process: Any) -> dict[str, Any]:
        assert process.stdout is not None
        while line := process.stdout.readline():
            for encoding in ("utf-8", "gb18030"):
                try:
                    response = json.loads(line.decode(encoding))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(response, dict):
                    return response
        raise EngineError("PaddleOCR-VL worker exited without a response.")

    def ocr(self, crop_path: Path, *, prompt: str | None = None) -> str:
        # PaddleOCR-VL exposes document-parsing tasks, not arbitrary chat prompts.
        del prompt
        process = self._start()
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write((json.dumps({"image_path": str(crop_path)}) + "\n").encode())
        process.stdin.flush()
        response = self._read_response(process)
        if error := response.get("error"):
            raise EngineError(f"PaddleOCR-VL inference failed for {crop_path}: {error}")
        text = response.get("text")
        if not isinstance(text, str) or not text.strip():
            raise EngineError("PaddleOCR-VL worker returned no markdown_texts for the crop.")
        return text.strip()

    def release(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._process.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            self._process.wait(timeout=10)
        self._process = None
