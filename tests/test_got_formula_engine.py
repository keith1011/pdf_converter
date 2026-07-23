from __future__ import annotations

from ocr_pipeline.engines.got_formula import GotFormulaEngine


def test_got_formula_engine_loads_lazily_once(tmp_path, monkeypatch):
    class Model:
        def chat(self, tokenizer, *, image_file, ocr_type):
            assert tokenizer == "fake-tokenizer"
            assert image_file.endswith("formula.png")
            assert ocr_type == "format"
            return "  x^2 + y^2  "

    import ocr_pipeline.engines.got_formula as mod

    loaded = []
    monkeypatch.setattr(
        mod,
        "_load_got_model",
        lambda **kwargs: loaded.append(kwargs) or (Model(), "fake-tokenizer"),
    )
    engine = GotFormulaEngine()
    crop = tmp_path / "formula.png"
    crop.write_bytes(b"x")

    assert loaded == []
    assert engine.ocr(crop) == "x^2 + y^2"
    assert engine.ocr(crop) == "x^2 + y^2"
    assert loaded == [{"model_id": "stepfun-ai/GOT-OCR2_0"}]
