"""LaTeX math cleanup helpers (frac, tokens, unicode supers)."""

from __future__ import annotations

import re

_SUPER = str.maketrans(
    {
        "⁰": "0",
        "¹": "1",
        "²": "2",
        "³": "3",
        "⁴": "4",
        "⁵": "5",
        "⁶": "6",
        "⁷": "7",
        "⁸": "8",
        "⁹": "9",
        "⁻": "-",
        "⁺": "+",
    }
)
_SUB = str.maketrans(
    {
        "₀": "0",
        "₁": "1",
        "₂": "2",
        "₃": "3",
        "₄": "4",
        "₅": "5",
        "₆": "6",
        "₇": "7",
        "₈": "8",
        "₉": "9",
    }
)

# Factor: (...)^k , \frac{}{}, id with scripts, number
_FACTOR = (
    r"(?:"
    r"\([^()]*\)(?:\^\{[^{}]*\}|\^\w)?|"
    r"\\frac\{[^{}]*\}\{[^{}]*\}|"
    r"\\[a-zA-Z]+(?:\{[^{}]*\})?|"
    r"[A-Za-z]+(?:_\{[^{}]*\}|_\w|\^\{[^{}]*\}|\^\w)*|"
    r"\d+(?:\^\{[^{}]*\}|\^\w)?"
    r")"
)
# Allow juxtaposition: (4)(5), m^{15}n^{-35}
_ATOM = rf"(?:{_FACTOR})+"


def strip_model_junk(text: str) -> str:
    text = re.sub(r"<\|[^|>]+\|>", "", text)
    text = re.sub(r"</?box>", "", text, flags=re.IGNORECASE)
    return text.strip()


def unicode_script_to_latex(expr: str) -> str:
    expr = re.sub(
        r"([A-Za-z0-9\)\]])([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)",
        lambda m: m.group(1) + "^{" + m.group(2).translate(_SUPER) + "}",
        expr,
    )
    expr = re.sub(
        r"([A-Za-z0-9\)\]])([₀₁₂₃₄₅₆₇₈₉]+)",
        lambda m: m.group(1) + "_{" + m.group(2).translate(_SUB) + "}",
        expr,
    )
    return expr


def slash_to_frac(expr: str) -> str:
    """
    Convert a/b to \\frac{a}{b}.

    Heuristic for mark-scheme OCR (e.g. 4a + 5b - 7 / b):
      if left of '/' contains + or - at top level, treat whole left as numerator.
    Otherwise convert local atoms (7/b).
    """
    expr = expr.strip()
    for _ in range(24):
        # Find a top-level slash
        depth = 0
        slash_at = -1
        spaced = False
        i = 0
        while i < len(expr):
            ch = expr[i]
            if ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth = max(0, depth - 1)
            elif depth == 0 and expr.startswith(" / ", i):
                slash_at = i
                spaced = True
                break
            elif depth == 0 and ch == "/" and not expr[i - 1 : i] == "\\":
                slash_at = i
                spaced = False
                break
            i += 1
        if slash_at < 0:
            break

        left = expr[:slash_at].rstrip()
        right = expr[slash_at + (3 if spaced else 1) :].lstrip()
        if not left or not right:
            break

        # If left has top-level +/-, take entire left as numerator;
        # right atom only (possibly juxtaposed factors).
        left_has_addsub = False
        depth = 0
        for j, ch in enumerate(left):
            if ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth = max(0, depth - 1)
            elif depth == 0 and ch in "+-" and j > 0:
                left_has_addsub = True
                break

        m_right = re.match(_ATOM, right)
        if not m_right:
            break
        num_right = m_right.group(0)
        rest = right[len(num_right) :]

        if left_has_addsub:
            num_left = left
        else:
            # take rightmost atom from left
            atoms = list(re.finditer(_ATOM, left))
            if not atoms:
                break
            last = atoms[-1]
            # ensure nothing but spaces after last atom
            if left[last.end() :].strip():
                # fallback whole left
                num_left = left
            else:
                num_left = last.group(0)
                prefix = left[: last.start()]
                expr = prefix + f"\\frac{{{num_left}}}{{{num_right}}}" + rest
                continue

        expr = f"\\frac{{{num_left}}}{{{num_right}}}" + rest
    return expr


def _fix_math_inner(inner: str) -> str:
    inner = unicode_script_to_latex(inner.strip())
    parts = re.split(r"(\s*=\s*)", inner)
    out: list[str] = []
    for p in parts:
        if re.fullmatch(r"\s*=\s*", p or ""):
            out.append(p)
        elif p.strip():
            out.append(slash_to_frac(p.strip()))
        else:
            out.append(p)
    return "".join(out)


def normalize_math_in_tex(tex: str) -> str:
    """Fix frac/scripts inside math delimiters. Unsafe across tabular — prefer sanitize_tex_document."""
    tex = strip_model_junk(tex)

    def repl_display(m: re.Match[str]) -> str:
        inner = _fix_math_inner(m.group(0).strip("$"))
        return f"$$\n{inner}\n$$"

    def repl_inline(m: re.Match[str]) -> str:
        inner = _fix_math_inner(m.group(1))
        return f"${inner}$"

    tex = re.sub(r"\$\$.*?\$\$", repl_display, tex, flags=re.DOTALL)
    tex = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", repl_inline, tex, flags=re.DOTALL)
    return tex


_TABULAR_RE = re.compile(
    r"\\begin\{(?:tabular\*?|longtable)\}.*?\\end\{(?:tabular\*?|longtable)\}",
    flags=re.DOTALL,
)
_BR_RE = re.compile(r"<br\s*/?>", flags=re.IGNORECASE)


def _sanitize_tabular(chunk: str) -> str:
    """Inside tabular: never $$; <br> → \\\\ ; still fix frac inside $...$."""
    chunk = _BR_RE.sub(r"\\\\", chunk)
    # Braces that contain \\ break tabular rows — flatten to ；
    chunk = re.sub(
        r"\{([^{}]*\\\\[^{}]*)\}",
        lambda m: "{" + re.sub(r"\s*\\\\\s*", "；", m.group(1)).strip() + "}",
        chunk,
    )

    def repl_display(m: re.Match[str]) -> str:
        inner = _fix_math_inner(m.group(0).strip("$"))
        return f"${inner}$"

    def repl_inline(m: re.Match[str]) -> str:
        inner = _fix_math_inner(m.group(1))
        return f"${inner}$"

    chunk = re.sub(r"\$\$.*?\$\$", repl_display, chunk, flags=re.DOTALL)
    chunk = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", repl_inline, chunk, flags=re.DOTALL)
    return chunk


def _mark_unpaired_dollars(tex: str) -> str:
    """Fail-open: odd count of single-$ → comment inside document; do not invent pairs."""
    without_display = re.sub(r"\$\$.*?\$\$", "", tex, flags=re.DOTALL)
    if without_display.count("$") % 2 != 1:
        return tex
    note = "% TODO: verify unpaired dollar"
    if note in tex:
        return tex
    # Keep comment inside the document so extract_tex_body / per-page merge retains it
    m = re.search(r"\\end\{document\}", tex, flags=re.IGNORECASE)
    if m:
        return tex[: m.start()] + note + "\n" + tex[m.start() :]
    return tex.rstrip() + "\n" + note + "\n"


def _ensure_table_packages(tex: str) -> str:
    """Inject longtable/array if used but missing from preamble."""
    if "\\begin{longtable}" not in tex:
        return tex
    if "\\usepackage{longtable" in tex or "\\usepackage{longtable," in tex:
        return tex
    if "longtable" in tex.split("\\begin{document}", 1)[0]:
        return tex
    insert = "\\usepackage{longtable,array}\n"
    m = re.search(r"(\\usepackage\{[^}]*\}\n)", tex)
    if m:
        return tex[: m.end()] + insert + tex[m.end() :]
    m2 = re.search(r"(\\documentclass(?:\[[^\]]*\])?\{[^}]*\}\n)", tex)
    if m2:
        return tex[: m2.end()] + insert + tex[m2.end() :]
    return insert + tex


def sanitize_tex_document(tex: str) -> str:
    """
    Compile-friendly post-pass (tabular-aware).

    - Stash tabular environments so body $$ DOTALL cannot cross cells
    - Inside tabular: $$ → $ ; <br> → \\\\
    - Outside tabular: <br> → blank line ; normalize display/inline math
    - Unpaired $ outside tables → % TODO: verify (fail-open)
    """
    tex = strip_model_junk(tex)
    tabs: list[str] = []

    def stash(m: re.Match[str]) -> str:
        tabs.append(_sanitize_tabular(m.group(0)))
        return f"<<<TABULAR{len(tabs) - 1}>>>"

    tex = _TABULAR_RE.sub(stash, tex)
    tex = _BR_RE.sub("\n\n", tex)
    tex = normalize_math_in_tex(tex)
    tex = _mark_unpaired_dollars(tex)
    for i, tab in enumerate(tabs):
        tex = tex.replace(f"<<<TABULAR{i}>>>", tab)
    return _ensure_table_packages(tex)
