"""TDD: code-review follow-ups (DR2, wrap_tex, unpaired TODO, VLM labels)."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.cli_report import WarnCollector
from ocr_pipeline.latex_math import sanitize_tex_document
from ocr_pipeline.pipeline import PipelineManager
from ocr_pipeline.routers import MathRouter

# --- RED targets ---


def test_wrap_tex_is_public_api():
    """Feature envy fix: callers must use public wrap_tex, not _wrap_tex."""
    assert hasattr(FinalPolisher, "wrap_tex")
    out = FinalPolisher.wrap_tex("hello")
    assert out.startswith("\\documentclass")
    assert "hello" in out
    assert "\\end{document}" in out


def test_unpaired_dollar_todo_stays_inside_document():
    """D3: % TODO must survive extract_tex_body + re-wrap (per-page merge)."""
    src = FinalPolisher.wrap_tex(r"price is $5 only")
    sanitized = sanitize_tex_document(src)
    assert "% TODO: verify unpaired dollar" in sanitized
    body = FinalPolisher.extract_tex_body(sanitized)
    assert "% TODO: verify unpaired dollar" in body
    merged = sanitize_tex_document(FinalPolisher.wrap_tex(body))
    assert "% TODO: verify unpaired dollar" in merged
    # comment must be before \\end{document}
    end = merged.lower().rfind("\\end{document}")
    todo = merged.rfind("% TODO: verify unpaired dollar")
    assert 0 <= todo < end


def test_pipeline_prints_stage3_start_once(monkeypatch, tmp_path: Path):
    """DR2=B: one Stage3 line even when polishing multiple pages."""
    calls: list[str] = []

    def fake_start() -> None:
        calls.append("stage3")

    monkeypatch.setattr("ocr_pipeline.pipeline.print_stage3_start", fake_start)

    class FakeLayout:
        _backend = "fullpage"

        def pdf_to_images(self, pdf_path, out_dir, *, limit=0):
            p1 = out_dir / "page_001.png"
            p2 = out_dir / "page_002.png"
            out_dir.mkdir(parents=True, exist_ok=True)
            p1.write_bytes(b"x")
            p2.write_bytes(b"x")
            return [p1, p2]

        def analyze_page(self, image_path, page):
            return []

        def release(self):
            pass

    class FakeRouter:
        def route_page(self, blocks):
            return blocks

    class FakeAssembler:
        def stitch(self, blocks):
            return "draft"

    class FakePolisher:
        def polish(self, draft):
            return "txt", FinalPolisher.wrap_tex("body"), []

        def extract_tex_body(self, tex):
            return FinalPolisher.extract_tex_body(tex)

        def wrap_tex(self, body):
            return FinalPolisher.wrap_tex(body)

    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF")
    out = tmp_path / "out"
    pages = tmp_path / "pages"
    mgr = PipelineManager(
        FakeLayout(),
        FakeRouter(),
        FakeAssembler(),
        FakePolisher(),
        output_dir=out,
        pages_dir=pages,
    )
    mgr.run(pdf, overwrite=True, warns=WarnCollector())
    assert calls == ["stage3"], f"expected one Stage3 start, got {calls!r}"


def test_math_router_requires_engine_or_vlm_fallback():
    r = MathRouter()
    try:
        r.extract_latex(Path("missing.png"))
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "formula engine" in str(exc).lower()


def test_math_router_vlm_fallback_used_when_no_formula_engine(tmp_path):
    crop = tmp_path / "c.png"
    crop.write_bytes(b"x")

    class FakeVlm:
        def generate(self, prompt, image_path=None, max_new_tokens=None):
            assert image_path == crop
            return "x^2"

    r = MathRouter(vlm_fallback=FakeVlm())
    assert "x^2" in r.extract_latex(crop)
