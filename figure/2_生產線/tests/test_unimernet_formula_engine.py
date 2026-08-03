from __future__ import annotations

import sys
from types import SimpleNamespace

from ocr_pipeline.engines.unimernet_formula import UnimernetFormulaEngine


def test_unimernet_formula_engine_loads_lazily_once(tmp_path, monkeypatch):
    class Model:
        def predict(self, formulas, image):
            assert formulas == [{"label": "display_formula", "bbox": [0, 0, 40, 20]}]
            assert image.shape == (20, 40, 3)
            return [{"latex": "  x^2 + y^2  "}]

    import ocr_pipeline.engines.unimernet_formula as mod

    loaded = []
    monkeypatch.setattr(
        mod,
        "_load_unimernet_model",
        lambda **kwargs: loaded.append(kwargs) or Model(),
    )
    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(imread=lambda path: SimpleNamespace(shape=(20, 40, 3))),
    )
    engine = UnimernetFormulaEngine()
    crop = tmp_path / "formula.png"
    crop.write_bytes(b"x")

    assert loaded == []
    assert engine.ocr(crop) == "x^2 + y^2"
    assert engine.ocr(crop) == "x^2 + y^2"
    assert loaded == [{"device": "cuda"}]
