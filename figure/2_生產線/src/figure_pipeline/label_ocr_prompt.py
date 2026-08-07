from __future__ import annotations

VISIBLE_LABEL_PROMPT_VERSION = "figure-b3-v3"

# Legacy v1 prompt. Keep this byte-stable so explicit v1 reruns remain reproducible.
VISIBLE_LABEL_PROMPT = """Inspect only the supplied figure crop.
Transcribe every visible label in natural reading order. Include Latin and
Greek letters, numbers, angle values, axis labels, legend text, table text,
and visible mathematical symbols. Preserve repeated visible occurrences.
Use exactly one kind per label from: latin_letter, greek_letter, number,
angle_value, axis_label, legend_text, table_text, math_symbol, text.
Do not solve the math problem. Do not describe the figure. Do not infer
geometric relations, hidden labels, values, or meanings that are not visibly
printed. Do not return Markdown, code fences, commentary, or extra keys.
Return exactly one unfenced JSON object in this shape:
{"labels":[{"text":"A","kind":"latin_letter"}],
 "confidence":0.0,"needs_review":true}
Use an empty labels array when no label is visible. confidence must be a number
from 0 to 1. needs_review must be true."""

VISIBLE_LABEL_PROMPT_V2 = """Inspect only the supplied figure crop.
Transcribe every visible label. Include Latin and Greek letters, numbers,
angle values, axis labels, legend text, table text, and visible mathematical
symbols. Preserve repeated visible occurrences.
Use exactly one kind per label from: latin_letter, greek_letter, number,
angle_value, axis_label, legend_text, table_text, math_symbol, text.
Use axis_label for text that names an axis or direction, including x, y, 北,
東, North, and East.
Return labels in visual scan order: top-to-bottom, then left-to-right within a
row. Do not sort alphabetically or group by kind. When a value or marker is
visibly adjacent to a vertex label, return the vertex label immediately before
that local value or marker.
Do not solve the math problem. Do not describe the figure. Do not infer
geometric relations, hidden labels, values, or meanings that are not visibly
printed. Do not return Markdown, code fences, commentary, or extra keys.
Return exactly one unfenced JSON object in this shape:
{"labels":[{"text":"A","kind":"latin_letter"}],
 "confidence":0.0,"needs_review":true}
Use an empty labels array when no label is visible. confidence must be a number
from 0 to 1 reflecting transcription certainty only. needs_review must be true."""

VISIBLE_LABEL_PROMPT_V3 = """Inspect only the supplied figure crop.
Transcribe every visible label. Include Latin and Greek letters, numbers,
angle values, axis labels, legend text, table text, and visible mathematical
symbols. Preserve repeated visible occurrences.
Return labels in visual scan order: top-to-bottom, then left-to-right within a
row. Do not sort alphabetically or group by kind.
Use exactly one kind per label from: latin_letter, greek_letter, number,
angle_value, axis_label, legend_text, table_text, math_symbol, text.
Use axis_label for an axis or compass-direction label such as x, y, 北, 東,
North, or East.
Do not solve the math problem. Do not describe the figure. Do not infer
geometric relations, hidden labels, values, or meanings that are not visibly
printed. Do not return Markdown, code fences, commentary, or extra keys.
Return exactly one unfenced JSON object in this shape:
{"labels":[{"text":"A","kind":"latin_letter"}],
 "confidence":0.85,"needs_review":true}
Estimate confidence from 0 to 1 as the probability that the entire labels
array, including text and kinds, is correct. Do not copy the example value.
Use 0 only when the transcription is unreadable or purely a guess.
Use an empty labels array when no label is visible. needs_review must be true."""

_VISIBLE_LABEL_PROMPTS = {
    "figure-b3-v1": VISIBLE_LABEL_PROMPT,
    "figure-b3-v2": VISIBLE_LABEL_PROMPT_V2,
    "figure-b3-v3": VISIBLE_LABEL_PROMPT_V3,
}


def get_visible_label_prompt(prompt_version: str) -> str:
    try:
        return _VISIBLE_LABEL_PROMPTS[prompt_version]
    except KeyError as exc:
        raise ValueError(f"unsupported prompt_version: {prompt_version}") from exc
