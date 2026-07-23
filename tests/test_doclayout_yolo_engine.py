from __future__ import annotations

from ocr_pipeline.engines.doclayout_yolo import (
    DocLayoutYoloEngine,
    map_doclayout_label,
)
from ocr_pipeline.models import BlockType


def test_doclayout_label_mapping():
    assert map_doclayout_label("formula") == BlockType.FORMULA
    assert map_doclayout_label("equation") == BlockType.EQUATION
    assert map_doclayout_label("title") == BlockType.TITLE
    assert map_doclayout_label("table") == BlockType.TABLE
    assert map_doclayout_label("plain text") == BlockType.TEXT
    assert map_doclayout_label("figure") == BlockType.OTHER


def test_doclayout_engine_is_lazy_and_maps_boxes(tmp_path, monkeypatch):
    class Value:
        def __init__(self, value):
            self.value = value

        def squeeze(self):
            return self

        def tolist(self):
            return self.value

        def __float__(self):
            return float(self.value)

        def __int__(self):
            return int(self.value)

    class Box:
        def __init__(self, coords, label):
            self.xyxy = Value(coords)
            self.cls = Value(label)
            self.conf = Value(0.91)

    class Result:
        names = {0: "plain text", 1: "formula"}
        boxes = [
            Box([50, 90, 100, 110], 0),
            Box([10, 20, 40, 40], 1),
        ]

    class Model:
        def predict(self, image_path, **kwargs):
            assert kwargs == {"imgsz": 1024, "conf": 0.2}
            return [Result()]

    import ocr_pipeline.engines.doclayout_yolo as mod

    loaded = []
    monkeypatch.setattr(
        mod, "_load_doclayout_model", lambda **kwargs: loaded.append(kwargs) or Model()
    )
    engine = DocLayoutYoloEngine()
    image = tmp_path / "page.png"

    assert loaded == []
    blocks = engine.analyze(image, page=2)
    assert loaded == [
        {
            "model_id": "juliozhao/DocLayout-YOLO-DocStructBench",
            "weights_file": "doclayout_yolo_docstructbench_imgsz1024.pt",
        }
    ]
    assert [block.block_type for block in blocks] == [BlockType.FORMULA, BlockType.TEXT]
    assert [block.order for block in blocks] == [0, 1]
    assert blocks[0].bbox.y1 == 20.0
