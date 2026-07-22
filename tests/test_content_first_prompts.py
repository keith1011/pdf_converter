"""TDD T5: content-first polish prompt contract."""

from __future__ import annotations

from ocr_pipeline.prompts import CONTENT_FIRST_POLISH_PROMPT, LATEX_MATH_RULES


def test_content_first_polish_forbids_image_meta_and_tabular_as_goal():
    p = CONTENT_FIRST_POLISH_PROMPT
    assert "將圖片" in p or "轉換為" in p  # must mention forbid meta
    assert "禁止" in p
    assert "tabular" in p.lower() or "表格" in p
    assert "完整" in p or "不要切開" in p or "中間" in p


def test_content_first_polish_requires_linear_dollar_math():
    p = CONTENT_FIRST_POLISH_PROMPT
    assert "$" in p
    assert "<<<TXT>>>" in p and "<<<TEX>>>" in p
    assert LATEX_MATH_RULES in p or "\\frac" in p


def test_final_polisher_uses_content_first_prompt():
    from ocr_pipeline.assemble import FinalPolisher
    from ocr_pipeline.prompts import CONTENT_FIRST_POLISH_PROMPT

    assert FinalPolisher.prompt_header() == CONTENT_FIRST_POLISH_PROMPT
