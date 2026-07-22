"""TDD T3: formula integrity — no mid-frac breaks, marks junk, bad commands."""

from __future__ import annotations

from ocr_pipeline.formula_integrity import check_math_body
from ocr_pipeline.models import IntegrityStatus


def test_feac_typo_is_repaired_to_frac():
    status, body, warnings = check_math_body(r"\feac{1}{6}")
    assert status is IntegrityStatus.REPAIRED
    assert body == r"\frac{1}{6}"
    assert warnings


def test_backslash_backslash_inside_frac_args_fails():
    status, body, warnings = check_math_body(r"\frac{1}{2\times 3}\\分")
    assert status is IntegrityStatus.FAIL
    assert any("frac" in w.lower() or "\\\\" in w for w in warnings)


def test_cjk_fen_inside_math_fails_or_flags():
    status, body, warnings = check_math_body(r"x=1分")
    assert status is IntegrityStatus.FAIL
    assert warnings
