"""TDD: multi-page polish strategy to avoid Stage3 CUDA OOM."""

from __future__ import annotations

from ocr_pipeline.pipeline import decide_polish_per_page


def test_single_short_page_uses_per_page_polish_for_pageir():
    assert decide_polish_per_page(page_count=1, draft_chars=500, requested=False) is True


def test_many_pages_auto_enables_per_page():
    assert decide_polish_per_page(page_count=14, draft_chars=2000, requested=False) is True


def test_long_draft_auto_enables_per_page():
    assert decide_polish_per_page(page_count=1, draft_chars=20_000, requested=False) is True


def test_explicit_request_still_true():
    assert decide_polish_per_page(page_count=1, draft_chars=100, requested=True) is True
