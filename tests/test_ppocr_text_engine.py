from __future__ import annotations

import sys

import pytest

from ocr_pipeline.engines.base import EngineError
from ocr_pipeline.engines.ppocr_text import PpocrTextEngine


def test_ppocr_engine_joins_lines_from_predict(tmp_path, monkeypatch):
    class FakeOCR:
        def predict(self, path):
            return [{"rec_texts": ["繁中", "第二行"], "rec_scores": [0.99, 0.98]}]

    import ocr_pipeline.engines.ppocr_text as mod

    monkeypatch.setattr(mod, "_load_paddle_ocr", lambda **kw: FakeOCR())
    eng = PpocrTextEngine()
    crop = tmp_path / "c.png"
    crop.write_bytes(b"x")

    assert eng.ocr(crop) == "繁中\n第二行"


def test_ppocr_engine_joins_legacy_ocr_tuples(tmp_path, monkeypatch):
    class FakeOCR:
        def ocr(self, path):
            return [
                [
                    [[0, 0], [1, 0], [1, 1], [0, 1]],
                    ("繁中", 0.99),
                ],
                [
                    [[0, 0], [1, 0], [1, 1], [0, 1]],
                    ("第二行", 0.98),
                ],
            ]

    import ocr_pipeline.engines.ppocr_text as mod

    monkeypatch.setattr(mod, "_load_paddle_ocr", lambda **kw: FakeOCR())
    eng = PpocrTextEngine()
    crop = tmp_path / "c.png"
    crop.write_bytes(b"x")

    assert eng.ocr(crop) == "繁中\n第二行"


def test_ppocr_is_loaded_lazily_once(tmp_path, monkeypatch):
    calls = []

    class FakeOCR:
        def predict(self, path):
            return []

    import ocr_pipeline.engines.ppocr_text as mod

    monkeypatch.setattr(mod, "_load_paddle_ocr", lambda **kw: calls.append(kw) or FakeOCR())
    crop = tmp_path / "c.png"
    crop.write_bytes(b"x")
    eng = PpocrTextEngine()

    assert calls == []
    eng.ocr(crop)
    eng.ocr(crop)
    assert calls == [{"lang": "chinese_cht"}]


def test_missing_paddleocr_raises_install_hint(monkeypatch):
    import ocr_pipeline.engines.ppocr_text as mod

    monkeypatch.setitem(sys.modules, "paddleocr", None)
    with pytest.raises(EngineError, match="uv sync --group got"):
        mod._load_paddle_ocr(lang="chinese_cht")
