from __future__ import annotations

import json
from pathlib import Path

import pytest

from figure_pipeline.classification_models import ClassificationProposal
from figure_pipeline.classification_parser import (
    ClassificationParseError,
    parse_classification_response,
)
from figure_pipeline.classification_prompt import (
    FIGURE_CLASSIFICATION_PROMPT,
    FIGURE_CLASSIFICATION_PROMPT_VERSION,
)

FIXTURES = Path(__file__).parent / "fixtures"
VALID_RAW = (FIXTURES / "qwen_geometry_response.txt").read_text(encoding="utf-8")
INVALID_RECORDED_RAW = (FIXTURES / "qwen_invalid_response.txt").read_text(encoding="utf-8")
FENCED_VALID_RAW = "```json" + chr(10) + VALID_RAW + "```"
EXTRA_KEY_RAW = json.dumps({**json.loads(VALID_RAW), "extra": 1})


def parse(raw: str) -> ClassificationProposal:
    return parse_classification_response(
        raw,
        model_id="Qwen/Qwen3-VL-8B-Instruct",
        quantization="4-bit",
        prompt_version="figure-b2-v1",
    )


def test_parser_adds_runtime_metadata_to_valid_response() -> None:
    result = parse(VALID_RAW)

    assert isinstance(result, ClassificationProposal)
    assert result.visual_family == "geometry"
    assert result.subtype == "triangle"
    assert result.secondary_tags == []
    assert result.confidence == 0.91
    assert result.evidence == [
        "Three visible straight edges form a triangle",
        "Angle markers are present",
    ]
    assert result.needs_review is True
    assert result.model_id == "Qwen/Qwen3-VL-8B-Instruct"
    assert result.quantization == "4-bit"
    assert result.prompt_version == "figure-b2-v1"


@pytest.mark.parametrize(
    "raw",
    [
        INVALID_RECORDED_RAW,
        FENCED_VALID_RAW,
        "classification: geometry",
        EXTRA_KEY_RAW,
        "[]",
    ],
)
def test_parser_rejects_non_contract_responses(raw: str) -> None:
    with pytest.raises(ClassificationParseError):
        parse(raw)


def test_parser_rejects_model_supplied_runtime_metadata() -> None:
    raw = VALID_RAW.replace(
        '"needs_review": true',
        '"needs_review": true, "model_id": "model-supplied"',
    )

    with pytest.raises(ClassificationParseError):
        parse(raw)


def test_parser_rejects_string_confidence() -> None:
    raw = VALID_RAW.replace('"confidence": 0.91', '"confidence": "0.91"')

    with pytest.raises(ClassificationParseError):
        parse(raw)


def test_prompt_is_versioned_and_enforces_crop_only_output() -> None:
    assert FIGURE_CLASSIFICATION_PROMPT_VERSION == "figure-b2-v1"
    assert "Inspect only the supplied figure crop" in FIGURE_CLASSIFICATION_PROMPT
    assert "Do not solve the math problem" in FIGURE_CLASSIFICATION_PROMPT
    assert "Do not transcribe OCR" in FIGURE_CLASSIFICATION_PROMPT
    assert "Do not return Markdown" in FIGURE_CLASSIFICATION_PROMPT
    assert "needs_review must be true" in FIGURE_CLASSIFICATION_PROMPT
