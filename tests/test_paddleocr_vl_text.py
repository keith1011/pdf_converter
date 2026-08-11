import io
import json
from pathlib import Path

import pytest

from ocr_pipeline.engines.base import EngineError
from ocr_pipeline.engines.paddleocr_vl_text import PaddleOcrVlTextEngine


class _Process:
    def __init__(self, reply: dict[str, str]) -> None:
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(json.dumps(reply).encode() + b"\n")
        self.terminated = False

    def poll(self):
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float) -> None:
        del timeout


def test_paddleocr_vl_engine_is_lazy_and_returns_markdown(monkeypatch, tmp_path: Path):
    python = tmp_path / "python.exe"
    worker = tmp_path / "worker.py"
    python.touch()
    worker.touch()
    process = _Process({"text": "題幹\nA. 1\nB. 2\nC. 3\nD. 4"})
    seen: list[list[str]] = []

    def start(command, **_kwargs):
        seen.append(command)
        return process

    engine = PaddleOcrVlTextEngine(
        python_executable=python,
        worker_path=worker,
        process_factory=start,
    )
    crop = tmp_path / "question.png"

    assert engine.ocr(crop) == "題幹\nA. 1\nB. 2\nC. 3\nD. 4"
    assert seen == [[str(python), str(worker), "--device", "gpu"]]
    assert json.loads(process.stdin.getvalue().decode()) == {"image_path": str(crop)}
    engine.release()
    assert process.terminated is True


def test_paddleocr_vl_engine_normalizes_cuda_device(tmp_path: Path):
    python = tmp_path / "python.exe"
    worker = tmp_path / "worker.py"
    python.touch()
    worker.touch()
    seen: list[list[str]] = []

    engine = PaddleOcrVlTextEngine(
        device="cuda",
        python_executable=python,
        worker_path=worker,
        process_factory=lambda command, **_kwargs: seen.append(command)
        or _Process({"text": "ok"}),
    )
    engine.ocr(tmp_path / "question.png")

    assert seen[0][-1] == "gpu"


def test_paddleocr_vl_engine_passes_low_memory_worker_options(tmp_path: Path):
    python = tmp_path / "python.exe"
    worker = tmp_path / "worker.py"
    python.touch()
    worker.touch()
    seen: list[list[str]] = []

    engine = PaddleOcrVlTextEngine(
        python_executable=python,
        worker_path=worker,
        process_factory=lambda command, **_kwargs: seen.append(command)
        or _Process({"text": "ok"}),
        use_layout_detection=False,
        max_pixels=1_048_576,
        precision="fp16",
    )
    engine.ocr(tmp_path / "question.png")

    assert seen == [
        [
            str(python),
            str(worker),
            "--device",
            "gpu",
            "--disable-layout-detection",
            "--max-pixels",
            "1048576",
            "--precision",
            "fp16",
        ]
    ]


def test_paddleocr_vl_engine_fails_loudly_when_runtime_is_missing(tmp_path: Path):
    with pytest.raises(EngineError, match="runtime is missing"):
        PaddleOcrVlTextEngine(python_executable=tmp_path / "python.exe").ocr(
            tmp_path / "question.png"
        )
