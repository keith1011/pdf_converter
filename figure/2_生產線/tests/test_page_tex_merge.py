"""Per-page TeX bodies must merge into a single document preamble."""

from __future__ import annotations

from ocr_pipeline.assemble import FinalPolisher


def test_extract_tex_body_strips_wrapper():
    full = FinalPolisher.wrap_tex(r"hello $$\frac{a}{b}$$")
    body = FinalPolisher.extract_tex_body(full)
    assert r"\documentclass" not in body
    assert "hello" in body
    assert r"\frac{a}{b}" in body


def test_merge_two_page_tex_one_documentclass():
    p1 = FinalPolisher.wrap_tex("page one")
    p2 = FinalPolisher.wrap_tex("page two")
    bodies = [FinalPolisher.extract_tex_body(p1), FinalPolisher.extract_tex_body(p2)]
    merged = FinalPolisher.wrap_tex("\n\n".join(bodies))
    assert merged.count(r"\documentclass") == 1
    assert merged.count(r"\begin{document}") == 1
    assert "page one" in merged and "page two" in merged
