"""OCR → vector quality gate: segment admit + doc report."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

QUALITY_SCHEMA = 1

_BARE_OPTION = re.compile(r"^[A-Da-d][.．]?\s*$")
_PUNCT_PAREN = re.compile(r"^[。．.、，,()（）\s]+$")
_SINGLE_CJK = re.compile(r"^[\u4e00-\u9fff]$")
_LONE_QNUM = re.compile(r"^\d{1,2}[.．]?\s*$")
_LATEXISH = re.compile(r"[\\$=]")

# Soft / hard thresholds (design v1)
_SOFT_LE3 = 0.15
_HARD_LE3 = 0.20
_SOFT_GE20 = 0.40
_HARD_GE20 = 0.35
_SOFT_BARE_OPT = 5
_HARD_BARE_OPT = 15
_SOFT_ADMITTED = 0.40
_HARD_ADMITTED = 0.25


def admit_segment(seg: dict[str, Any]) -> bool:
    """Layer A: True if segment is retrieval-useful enough to embed."""
    text = (seg.get("text") or "").strip()
    if not text:
        return False
    if _BARE_OPTION.fullmatch(text):
        return False
    if _PUNCT_PAREN.fullmatch(text):
        return False
    if _SINGLE_CJK.fullmatch(text) or _LONE_QNUM.fullmatch(text):
        return False

    kind = str(seg.get("kind") or "prose").lower()
    n = len(text)

    if kind == "figure":
        crop = seg.get("crop_path") or seg.get("crop_relpath")
        return n >= 4 and bool(crop)

    if kind == "math":
        if n >= 8 and _LATEXISH.search(text):
            return True
        return n >= 12

    if kind == "mark_note":
        return n >= 8

    # prose + unknown → prose floor
    return n >= 12


def _iter_segments(pageir_or_segments: Any) -> list[dict[str, Any]]:
    if isinstance(pageir_or_segments, list):
        return [s for s in pageir_or_segments if isinstance(s, dict)]
    if isinstance(pageir_or_segments, dict):
        pages = pageir_or_segments.get("pages") or []
        out: list[dict[str, Any]] = []
        for page in pages:
            out.extend(page.get("segments") or [])
        return out
    return []


def build_quality_report(
    pageir_or_segments: Any,
    *,
    doc_id: str,
) -> dict[str, Any]:
    """Layer B: metrics + verdict for a PageIR document."""
    segs = _iter_segments(pageir_or_segments)
    n = len(segs)
    texts = [(s.get("text") or "").strip() for s in segs]

    le3 = sum(1 for t in texts if len(t) <= 3)
    ge20 = sum(1 for t in texts if len(t) >= 20)
    ge40 = sum(1 for t in texts if len(t) >= 40)
    bare_opt = sum(1 for t in texts if _BARE_OPTION.fullmatch(t))
    punct = sum(1 for t in texts if _PUNCT_PAREN.fullmatch(t))
    single_cjk = sum(1 for t in texts if _SINGLE_CJK.fullmatch(t))
    n_figure = sum(1 for s in segs if str(s.get("kind") or "").lower() == "figure")
    n_version = sum(1 for s in segs if s.get("version_id"))
    admitted = sum(1 for s in segs if admit_segment(s))

    pct_le3 = (le3 / n) if n else 1.0
    pct_ge20 = (ge20 / n) if n else 0.0
    pct_ge40 = (ge40 / n) if n else 0.0
    pct_admitted = (admitted / n) if n else 0.0

    fail_reasons: list[str] = []
    warn_reasons: list[str] = []

    if n < 1:
        fail_reasons.append("n_segments<1")
    if pct_le3 > _HARD_LE3:
        fail_reasons.append("pct_le3>0.20")
    elif pct_le3 > _SOFT_LE3:
        warn_reasons.append("pct_le3>0.15")

    if pct_ge20 < _HARD_GE20:
        fail_reasons.append("pct_ge20<0.35")
    elif pct_ge20 < _SOFT_GE20:
        warn_reasons.append("pct_ge20<0.40")

    if bare_opt > _HARD_BARE_OPT:
        fail_reasons.append("bare_option_only>15")
    elif bare_opt > _SOFT_BARE_OPT:
        warn_reasons.append("bare_option_only>5")

    if pct_admitted < _HARD_ADMITTED:
        fail_reasons.append("pct_admitted_est<0.25")
    elif pct_admitted < _SOFT_ADMITTED:
        warn_reasons.append("pct_admitted_est<0.40")

    if fail_reasons:
        verdict = "fail"
    elif warn_reasons:
        verdict = "warn"
    else:
        verdict = "pass"

    return {
        "quality_schema": QUALITY_SCHEMA,
        "doc_id": doc_id,
        "n_segments": n,
        "pct_le3": round(pct_le3, 3),
        "pct_ge20": round(pct_ge20, 3),
        "pct_ge40": round(pct_ge40, 3),
        "bare_option_only": bare_opt,
        "punct_or_paren_only": punct,
        "single_cjk_only": single_cjk,
        "n_figure": n_figure,
        "n_with_version_id": n_version,
        "pct_admitted_est": round(pct_admitted, 3),
        "verdict": verdict,
        "fail_reasons": fail_reasons,
        "warn_reasons": warn_reasons,
    }


def write_quality_json(path: Path, report: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
