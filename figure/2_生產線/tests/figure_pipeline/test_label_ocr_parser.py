from __future__ import annotations

import json
from pathlib import Path

import pytest

from figure_pipeline.label_ocr_models import VisibleLabelProposal
from figure_pipeline.label_ocr_parser import (
    VisibleLabelParseError,
    parse_visible_label_response,
)
from figure_pipeline.label_ocr_prompt import (
    VISIBLE_LABEL_PROMPT,
)

FIXTURES = Path(__file__).parent / "fixtures"
VALID_RAW = (FIXTURES / "qwen_visible_labels_response.txt").read_text(encoding="utf-8")
FENCED_VALID_RAW = "```json" + chr(10) + VALID_RAW + "```"
VALID_PAYLOAD = json.loads(VALID_RAW)
EXTRA_KEY_RAW = json.dumps({**VALID_PAYLOAD, "extra": 1}, ensure_ascii=False)
MISSING_KEY_RAW = json.dumps(
    {key: value for key, value in VALID_PAYLOAD.items() if key != "confidence"},
    ensure_ascii=False,
)


def parse(raw: str) -> VisibleLabelProposal:
    return parse_visible_label_response(
        raw,
        model_id="Qwen/Qwen3-VL-8B-Instruct",
        quantization="4-bit",
        prompt_version="figure-b3-v1",
    )


def test_parser_adds_runtime_metadata_to_valid_response() -> None:
    result = parse(VALID_RAW)

    assert isinstance(result, VisibleLabelProposal)
    assert [label.text for label in result.labels] == ["B", "β", "C", "A", "α", "D"]
    assert [label.kind for label in result.labels] == [
        "latin_letter",
        "greek_letter",
        "latin_letter",
        "latin_letter",
        "greek_letter",
        "latin_letter",
    ]
    assert result.confidence == 0.94
    assert result.needs_review is True
    assert result.model_id == "Qwen/Qwen3-VL-8B-Instruct"
    assert result.quantization == "4-bit"
    assert result.prompt_version == "figure-b3-v1"


@pytest.mark.parametrize(
    "prompt_version",
    ["figure-b3-v1", "figure-b3-v2", "figure-b3-v3"],
)
def test_parser_accepts_current_and_legacy_b3_prompt_versions(
    prompt_version: str,
) -> None:
    result = parse_visible_label_response(
        VALID_RAW,
        model_id="Qwen/Qwen3-VL-8B-Instruct",
        quantization="4-bit",
        prompt_version=prompt_version,
    )

    assert result.prompt_version == prompt_version


@pytest.mark.parametrize(
    "raw",
    [
        FENCED_VALID_RAW,
        "visible labels: B, β, C, A, α, D",
        json.dumps([]),
        EXTRA_KEY_RAW,
        MISSING_KEY_RAW,
    ],
)
def test_parser_rejects_non_contract_responses(raw: str) -> None:
    with pytest.raises(VisibleLabelParseError):
        parse(raw)


@pytest.mark.parametrize(
    "raw",
    [
        VALID_RAW.replace('"confidence": 0.94', '"confidence": "0.94"'),
        VALID_RAW.replace('"confidence": 0.94', '"confidence": true'),
        VALID_RAW.replace('"needs_review": true', '"needs_review": false'),
        VALID_RAW.replace('"kind": "latin_letter"', '"kind": "unknown_kind"'),
        VALID_RAW.replace('"text": "B"', '"text": "B\\nC"'),
    ],
)
def test_parser_rejects_invalid_label_or_control_values(raw: str) -> None:
    with pytest.raises(VisibleLabelParseError):
        parse(raw)


def test_prompt_is_versioned_and_requires_crop_only_label_transcription() -> None:
    prompt = VISIBLE_LABEL_PROMPT.lower()

    assert "figure crop" in prompt
    assert "transcrib" in prompt
    assert "do not solve" in prompt
    assert "geometric relation" in prompt
    assert "exactly one unfenced json object" in prompt
    assert "markdown" in prompt
    assert "needs_review" in prompt
    assert "true" in prompt
