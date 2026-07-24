from __future__ import annotations

from ocr_pipeline.engines.mineru_layout import MineruLayoutEngine
from ocr_pipeline.models import BlockType


def test_mineru_layout_engine_loads_lazily_and_sorts_blocks(tmp_path, monkeypatch):
    class Model:
        def predict(self, image):
            assert getattr(image, "mode", None) == "RGB"
            return [
                {"label": "text", "bbox": [20, 80, 100, 110], "score": 0.8},
                {"label": "display_formula", "bbox": [10, 20, 90, 50], "score": 0.9},
            ]

    from PIL import Image

    import ocr_pipeline.engines.mineru_layout as mod

    loaded = []
    monkeypatch.setattr(
        mod, "_load_mineru_layout_model", lambda **kwargs: loaded.append(kwargs) or Model()
    )
    engine = MineruLayoutEngine()
    image = tmp_path / "page.png"
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(image)

    assert loaded == []
    blocks = engine.analyze(image, page=2)
    assert loaded == [{"device": "cuda"}]
    assert [block.block_type for block in blocks] == [BlockType.FORMULA, BlockType.TEXT]
    assert [block.order for block in blocks] == [0, 1]
    assert blocks[0].bbox.y1 == 20.0


def test_mineru_layout_maps_figure_labels(tmp_path, monkeypatch):
    class Model:
        def predict(self, image):
            return [
                {"label": "image", "bbox": [0, 0, 10, 10]},
                {"label": "figure", "bbox": [0, 20, 10, 30]},
                {"label": "picture", "bbox": [0, 40, 10, 50]},
            ]

    from PIL import Image

    import ocr_pipeline.engines.mineru_layout as mod

    monkeypatch.setattr(mod, "_load_mineru_layout_model", lambda **kwargs: Model())
    engine = MineruLayoutEngine()
    image = tmp_path / "page.png"
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(image)
    blocks = engine.analyze(image, page=1)
    assert [b.block_type for b in blocks] == [
        BlockType.FIGURE,
        BlockType.FIGURE,
        BlockType.FIGURE,
    ]
