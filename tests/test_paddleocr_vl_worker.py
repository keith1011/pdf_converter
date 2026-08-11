import io
import json
import sys
from types import SimpleNamespace

from scripts import paddleocr_vl_worker


def test_worker_applies_low_memory_crop_options(monkeypatch, tmp_path, capsys):
    calls: dict[str, object] = {}

    class FakePipeline:
        def __init__(self, **kwargs) -> None:
            calls["init"] = kwargs

        def predict(self, image_path: str, **kwargs):
            calls["predict"] = (image_path, kwargs)
            return [SimpleNamespace(markdown={"markdown_texts": "ok"})]

    crop = tmp_path / "question.png"
    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        SimpleNamespace(PaddleOCRVL=FakePipeline),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "paddleocr_vl_worker.py",
            "--device",
            "gpu",
            "--disable-layout-detection",
            "--max-pixels",
            "1048576",
            "--precision",
            "fp16",
        ],
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"image_path": str(crop)}) + "\n"),
    )

    assert paddleocr_vl_worker.main() == 0
    assert calls["init"] == {
        "pipeline_version": "v1.6",
        "device": "gpu",
        "use_layout_detection": False,
        "precision": "fp16",
    }
    assert calls["predict"] == (str(crop), {"max_pixels": 1_048_576})
    assert json.loads(capsys.readouterr().out) == {"text": "ok"}
