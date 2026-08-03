"""Formula integrity checks for content-first math segments."""

from __future__ import annotations

import re

from .models import IntegrityStatus

# v1 typo map (capped; eng plan <=10)
_TYPO_MAP: dict[str, str] = {
    r"\feac": r"\frac",
    r"\fraq": r"\frac",
    r"\tims": r"\times",
}

_FRAC_CMDS = (r"\frac", r"\dfrac", r"\tfrac")
_CJK_FEN = "\u5206"  # 分
_BARE_1M_1A = re.compile(r"(?<![A-Za-z0-9])1[MA](?![A-Za-z0-9])")


def _scan_balanced_brace(s: str, start: int) -> int | None:
    """Return index after closing '}' for '{' at start, or None if unbalanced."""
    if start >= len(s) or s[start] != "{":
        return None
    depth = 0
    i = start
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def _frac_args_contain_double_backslash(body: str) -> bool:
    """True if \\\\ appears inside any \\frac/\\dfrac/\\tfrac brace argument."""
    i = 0
    n = len(body)
    while i < n:
        matched = None
        for cmd in _FRAC_CMDS:
            if body.startswith(cmd, i) and (
                i + len(cmd) >= n or not body[i + len(cmd)].isalpha()
            ):
                matched = cmd
                break
        if matched is None:
            i += 1
            continue
        j = i + len(matched)
        for _ in range(2):
            while j < n and body[j].isspace():
                j += 1
            end = _scan_balanced_brace(body, j)
            if end is None:
                return False
            arg = body[j + 1 : end - 1]
            if r"\\" in arg:
                return True
            j = end
        i = j
    return False


def check_math_body(body: str) -> tuple[IntegrityStatus, str, list[str]]:
    """
    Repair known typos in a math body (no outer $).

    Returns (status, maybe_repaired_body, warnings).
    Fail conditions (checked after repair) take priority over REPAIRED.
    """
    warnings: list[str] = []
    out = body
    repaired = False
    for bad, good in _TYPO_MAP.items():
        if bad in out:
            out = out.replace(bad, good)
            repaired = True
            warnings.append(f"repaired typo {bad} -> {good}")

    fail = False

    if _frac_args_contain_double_backslash(out):
        warnings.append(r"\\\\ inside frac/dfrac/tfrac argument")
        fail = True
    elif r"\\" in out and any(cmd in out for cmd in _FRAC_CMDS):
        # Mid-formula break after/near a frac (e.g. \frac{a}{b}\\...)
        warnings.append(r"\\\\ near frac (mid-formula break)")
        fail = True

    if _CJK_FEN in out:
        warnings.append("CJK fen in math body")
        fail = True

    if _BARE_1M_1A.search(out):
        warnings.append("bare 1M/1A pattern in math body")
        fail = True

    if re.search(
        r"\\(?:begin|end)\{(?:table\*?|tabular\*?|longtable)\}|\\hline\b",
        out,
        flags=re.IGNORECASE,
    ):
        warnings.append("tabular/table chrome in math body")
        fail = True

    if fail:
        return IntegrityStatus.FAIL, out, warnings
    if repaired:
        return IntegrityStatus.REPAIRED, out, warnings
    return IntegrityStatus.OK, out, warnings
