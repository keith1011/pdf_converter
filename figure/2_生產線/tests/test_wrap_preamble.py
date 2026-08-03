"""TDD: wrap_tex preamble must support longtable from Stage3."""

from __future__ import annotations

from ocr_pipeline.assemble import FinalPolisher


def test_wrap_tex_includes_longtable_package():
    tex = FinalPolisher.wrap_tex("\\begin{longtable}{c} x \\end{longtable}")
    preamble = tex.split("\\begin{document}")[0]
    assert "\\usepackage{longtable,array}" in preamble


def test_sanitize_injects_longtable_if_missing():
    from ocr_pipeline.latex_math import sanitize_tex_document

    raw = (
        "\\documentclass{ctexart}\n"
        "\\usepackage{amsmath}\n"
        "\\begin{document}\n"
        "\\begin{longtable}{c} a \\end{longtable}\n"
        "\\end{document}\n"
    )
    out = sanitize_tex_document(raw)
    assert "\\usepackage{longtable,array}" in out
