from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .label_ocr_models import VisibleLabelProposal

_RESPONSE_KEYS = frozenset({"labels", "confidence", "needs_review"})


class VisibleLabelParseError(ValueError):
    pass


def parse_visible_label_response(
    raw: str,
    *,
    model_id: str,
    quantization: str,
    prompt_version: str,
) -> VisibleLabelProposal:
    text = (raw or "").strip()
    fence = chr(96) * 3
    if not text or text.startswith(fence) or text.endswith(fence):
        raise VisibleLabelParseError("response must be one unfenced JSON object")
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VisibleLabelParseError("response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise VisibleLabelParseError("response root must be a JSON object")
    if set(payload) != _RESPONSE_KEYS:
        raise VisibleLabelParseError("response keys do not match the B3 contract")
    confidence = payload["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise VisibleLabelParseError("confidence must be a JSON number")

    proposal_payload = dict(payload)
    proposal_payload.update(
        {
            "model_id": model_id,
            "quantization": quantization,
            "prompt_version": prompt_version,
        }
    )
    try:
        return VisibleLabelProposal.model_validate(proposal_payload)
    except ValidationError as exc:
        raise VisibleLabelParseError("response violates the B3 label contract") from exc
