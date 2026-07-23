from __future__ import annotations

from ocr_pipeline.engines.got_formula import GotFormulaEngine


def test_got_formula_engine_loads_lazily_once(tmp_path, monkeypatch):
    class FakeTensor:
        def __init__(self, shape):
            self.shape = shape

        def __getitem__(self, key):
            return [1, 2, 3]

    class FakeInputs(dict):
        def to(self, device):
            return self

    class Processor:
        tokenizer = object()

        def __call__(self, path, **kwargs):
            assert kwargs.get("format") is True
            return FakeInputs(input_ids=FakeTensor((1, 3)))

        def decode(self, tokens, skip_special_tokens=True):
            return "  x^2 + y^2  "

    class Model:
        device = "cpu"

        def generate(self, **kwargs):
            assert kwargs.get("do_sample") is False
            return FakeTensor((1, 6))

    import ocr_pipeline.engines.got_formula as mod

    loaded = []
    monkeypatch.setattr(
        mod,
        "_load_got_model",
        lambda **kwargs: loaded.append(kwargs) or (Model(), Processor()),
    )
    engine = GotFormulaEngine()
    crop = tmp_path / "formula.png"
    crop.write_bytes(b"x")

    assert loaded == []
    assert engine.ocr(crop) == "x^2 + y^2"
    assert engine.ocr(crop) == "x^2 + y^2"
    assert loaded == [{"model_id": "stepfun-ai/GOT-OCR-2.0-hf"}]
