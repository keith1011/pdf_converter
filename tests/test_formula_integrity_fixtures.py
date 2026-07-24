"""TDD: formula_integrity fixtures (≥10 cases)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocr_pipeline.formula_integrity import check_math_body
from ocr_pipeline.models import IntegrityStatus

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "formula_integrity"


def _load_cases() -> list[dict]:
    path = _FIXTURES / "cases.jsonl"
    assert path.is_file(), f"missing fixtures file: {path}"
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    return cases


def test_formula_integrity_fixtures_at_least_ten():
    cases = _load_cases()
    assert len(cases) >= 10


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_formula_integrity_fixture_case(case: dict):
    status, body, _warnings = check_math_body(case["body"])
    assert status is IntegrityStatus(case["expect_status"])
    if "expect_body" in case:
        assert body == case["expect_body"]
