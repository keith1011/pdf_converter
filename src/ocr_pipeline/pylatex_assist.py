"""Post-polish LaTeX helpers via pylatexenc (not a VLM tool — deterministic encode)."""

from __future__ import annotations

import re

from .latex_math import unicode_script_to_latex

# Split keeping math spans ($$...$$ or $...$) so we never rewrite inside them.
_MATH_SPLIT = re.compile(r"(\$\$.*?\$\$|\$[^$]*\$)", re.DOTALL)


def encode_unicode_outside_math(text: str) -> str:
    """
    Convert leftover Unicode math/symbols to LaTeX *outside* ``$...$`` / ``$$...$$``.

    Order: script chars (²→^{2}) via existing helper, then pylatexenc for Greek etc.
    Existing LaTeX commands inside math delimiters are left untouched.

    CJK and other unmapped chars are **kept** (``unknown_char_policy='keep'``) with
    warnings disabled — otherwise every Chinese character floods the log and slows polish.
    """
    if not text:
        return text
    try:
        from pylatexenc.latexencode import UnicodeToLatexEncoder
    except ImportError:
        return unicode_script_to_latex(text)

    encoder = UnicodeToLatexEncoder(
        non_ascii_only=True,
        unknown_char_policy="keep",
        unknown_char_warning=False,
    )
    parts: list[str] = []
    for chunk in _MATH_SPLIT.split(text):
        if not chunk:
            continue
        if chunk.startswith("$"):
            parts.append(chunk)
            continue
        converted = unicode_script_to_latex(chunk)
        parts.append(encoder.unicode_to_latex(converted))
    return "".join(parts)
