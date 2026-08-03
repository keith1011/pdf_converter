"""Unit tests for tabular-aware TeX sanitize (T1)."""

from __future__ import annotations

from ocr_pipeline.latex_math import sanitize_tex_document


def test_tabular_display_math_becomes_inline():
    src = r"""
\begin{tabular}{cc}
A & $$\frac{a}{b}$$ \\
\end{tabular}
"""
    out = sanitize_tex_document(src)
    assert "$$" not in out
    assert r"$\frac{a}{b}$" in out
    assert r"\begin{tabular}" in out


def test_dotall_does_not_merge_across_cells():
    """Regression: global $$ DOTALL used to eat from cell1 through cell2."""
    src = r"""
\begin{tabular}{cc}
$$\frac{1}{2}$$ & $$\frac{3}{4}$$ \\
\end{tabular}
"""
    out = sanitize_tex_document(src)
    assert out.count(r"\frac{1}{2}") == 1
    assert out.count(r"\frac{3}{4}") == 1
    assert "$$" not in out
    # both cells still present as inline math
    assert r"$\frac{1}{2}$" in out
    assert r"$\frac{3}{4}$" in out


def test_br_inside_table_becomes_linebreak():
    src = r"""
\begin{tabular}{c}
hello<br>world \\
\end{tabular}
"""
    out = sanitize_tex_document(src)
    assert "<br>" not in out.lower()
    assert r"\\" in out


def test_br_outside_table_becomes_blank_line():
    src = "line1<br>line2"
    out = sanitize_tex_document(src)
    assert "<br>" not in out.lower()
    assert "line1" in out and "line2" in out
    assert "\n\n" in out


def test_body_display_math_kept():
    src = r"Before $$\frac{x}{y}$$ after"
    out = sanitize_tex_document(src)
    assert "$$" in out
    assert r"\frac{x}{y}" in out


def test_unpaired_dollar_fail_open():
    src = r"price is $5 only"
    out = sanitize_tex_document(src)
    assert "% TODO: verify unpaired dollar" in out


def test_tabular_brace_with_rowbreak_flattened():
    import re

    src = r"""
\begin{tabular}{cc}
1A & {1M 给分子\\
1M 给分母} \\
\end{tabular}
"""
    out = sanitize_tex_document(src)
    assert "；" in out
    assert not re.search(r"\{[^}]*\\\\[^}]*\}", out)


def test_tabular_star_supported():
    src = r"""
\begin{tabular*}{\textwidth}{cc}
$$a$$ & b \\
\end{tabular*}
"""
    out = sanitize_tex_document(src)
    assert "$$" not in out
    assert "$a$" in out
