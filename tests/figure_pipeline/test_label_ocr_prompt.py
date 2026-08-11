from __future__ import annotations

import re

import figure_pipeline.label_ocr_prompt as prompt_module


def prompt_for(version: str) -> str:
    resolver = getattr(prompt_module, "get_visible_label_prompt", None)
    assert callable(resolver), "B3 prompt versions require get_visible_label_prompt()"
    return resolver(version)


def test_v3_is_the_default_visible_label_prompt() -> None:
    assert prompt_module.VISIBLE_LABEL_PROMPT_VERSION == "figure-b3-v3"
    assert prompt_for(prompt_module.VISIBLE_LABEL_PROMPT_VERSION) != prompt_module.VISIBLE_LABEL_PROMPT


def test_v1_prompt_remains_byte_stable_for_existing_artifacts() -> None:
    assert prompt_for("figure-b3-v1") == prompt_module.VISIBLE_LABEL_PROMPT


def test_v3_prompt_defines_axis_labels_order_and_confidence_policy() -> None:
    prompt = prompt_for("figure-b3-v3").lower()

    assert "axis_label" in prompt
    assert "北" in prompt
    assert "東" in prompt
    assert "top-to-bottom" in prompt
    assert "left-to-right" in prompt
    assert "alphabet" in prompt
    assert "group by kind" in prompt
    assert "value or marker" not in prompt
    assert re.search(r'"confidence"\s*:\s*0\.(?!0\b)[0-9]+', prompt)
    assert "use 0 only" in prompt
    assert "unreadable" in prompt
    assert "guess" in prompt
