from __future__ import annotations

from ocr_pipeline.engines.mineru_layout import MineruLayoutEngine
from ocr_pipeline.models import BlockType


def test_mineru_layout_engine_loads_lazily_and_sorts_blocks(tmp_path, monkeypatch):
    class Model:
        def predict(self, image_path):
            assert image_path.endswith("page.png")
            return [
                {"label": "text", "bbox": [20, 80, 100, 110], "score": 0.8},
                {"label": "display_formula", "bbox": [10, 20, 90, 50], "score": 0.9},
            ]

    import ocr_pipeline.engines.mineru_layout as mod

    loaded = []
    monkeypatch.setattr(
        mod, "_load_mineru_layout_model", lambda **kwargs: loaded.append(kwargs) or Model()
    )
    engine = MineruLayoutEngine()
    image = tmp_path / "page.png"

    assert loaded == []
    blocks = engine.analyze(image, page=2)
    assert loaded == [{"device": "cuda"}]
    assert [block.block_type for block in blocks] == [BlockType.FORMULA, BlockType.TEXT]
    assert [block.order for block in blocks] == [0, 1]
    assert blocks[0].bbox.y1 == 20.0
