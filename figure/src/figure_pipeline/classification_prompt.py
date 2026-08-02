from __future__ import annotations

from .classification_models import SUBTYPE_BY_FAMILY

FIGURE_CLASSIFICATION_PROMPT_VERSION = "figure-b2-v1"

_FAMILIES = (
    "geometry, coordinate_graph, function_graph, statistical_chart, "
    "table, physical_diagram, illustration, unknown"
)
_SUBTYPES = "; ".join(
    f"{family}: {', '.join(sorted(values))}" for family, values in SUBTYPE_BY_FAMILY.items()
)

FIGURE_CLASSIFICATION_PROMPT = f"""Inspect only the supplied figure crop.
Choose exactly one visual_family from: {_FAMILIES}.
Choose one compatible subtype from this list: {_SUBTYPES}.
Use secondary_tags only for additional visibly present families; use at most three.
If the crop is ambiguous, incomplete, or not a supported figure, use
visual_family="unknown" and subtype="unclassified".
Do not solve the math problem. Do not transcribe OCR. Do not return Markdown,
code fences, commentary, or keys outside the required JSON object.
Return exactly this JSON shape:
{{"visual_family":"unknown", "subtype":"unclassified", "secondary_tags":[],
  "confidence":0.0, "evidence":["short observable cue"], "needs_review":true}}
The confidence is a number from 0 to 1. Evidence must contain one to three
short observable cues. needs_review must be true."""
