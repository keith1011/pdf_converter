from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .classification_models import ClassificationProposal

_RESPONSE_KEYS = frozenset(
    {
        "visual_family",
        "subtype",
        "secondary_tags",
        "confidence",
        "evidence",
        "needs_review",
    }
)


class ClassificationParseError(ValueError):
    pass


def parse_classification_response(
    raw: str,
    *,
    model_id: str,
    quantization: str,
    prompt_version: str,
) -> ClassificationProposal:
    text = (raw or "").strip()
    fence = chr(96) * 3
    if not text or text.startswith(fence) or text.endswith(fence):
        raise ClassificationParseError("response must be one unfenced JSON object")
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ClassificationParseError("response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ClassificationParseError("response root must be a JSON object")
    if set(payload) != _RESPONSE_KEYS:
        raise ClassificationParseError("response keys do not match the B2 contract")
    confidence = payload["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ClassificationParseError("confidence must be a JSON number")

    proposal_payload = dict(payload)
    proposal_payload.update(
        {
            "model_id": model_id,
            "quantization": quantization,
            "prompt_version": prompt_version,
        }
    )
    try:
        return ClassificationProposal.model_validate(proposal_payload)
    except ValidationError as exc:
        raise ClassificationParseError("response violates B2 taxonomy") from exc
