"""Structured Stage2 OCR for DSE Paper 2 MCQ crops."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

_FIGURE_LABEL_PREFIX = "圖中標示："
_STRUCTURED_PROMPT_SUFFIX = """

Return only the structured fields required by the response schema.
- Do not return or infer question_id; it is supplied by Stage1 metadata.
- choices must contain exactly A, B, C, and D.
- visible_figure_labels contains only labels visibly printed in a figure, never a description.
- Put unreadable or ambiguous image tokens in uncertain_tokens.
- Do not solve the question or infer missing mathematical content.
""".strip()

_OPTION_LINE = re.compile(r"^\s*([A-D])\s*[.．:：]\s*(.*)$")
_QUESTION_OPENER = re.compile(r"^\s*\d{1,2}\s*[.．:：]\s*")

def _join_ocr_lines(parts: list[str]) -> str:
    """join PDF layout lines into one natural sentence."""
    text = " ".join(part.strip() for part in parts if part.strip())

        # 中文標點前面不要有空格
    text = re.sub(r"\s+([，。；：！？、）】」』])", r"\1", text)

        # 中文標點或左括號後面不要有空格
    text = re.sub(r"([，。；：！？、（【「『])\s+", r"\1", text)

    return text.strip()

class McqChoices(BaseModel):
    """Exactly the four visible answer choices."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    A: str = Field(min_length=1)
    B: str = Field(min_length=1)
    C: str = Field(min_length=1)
    D: str = Field(min_length=1)


class McqOcrResult(BaseModel):
    """Validated OCR content for one Stage1-selected MCQ crop."""

    model_config = ConfigDict(extra="forbid")

    stem: str = Field(min_length=1)
    choices: McqChoices
    visible_figure_labels: list[str] = Field(default_factory=list)
    uncertain_tokens: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool = False

    @model_validator(mode="after")
    def uncertain_content_requires_review(self) -> McqOcrResult:
        if self.uncertain_tokens:
            self.requires_review = True
        return self


def render_text(question_id: int, result: McqOcrResult) -> str:
    """Render structured OCR back to the existing deterministic Stage2 text format."""
    qid = int(question_id)
    lines = [f"{qid}. {result.stem.strip()}"]
    labels = [label.strip() for label in result.visible_figure_labels if label.strip()]
    if labels:
        lines.append(_FIGURE_LABEL_PREFIX + "、".join(labels))
    choices = result.choices
    lines.extend(
        (
            f"A. {choices.A.strip()}",
            f"B. {choices.B.strip()}",
            f"C. {choices.C.strip()}",
            f"D. {choices.D.strip()}",
        )
    )
    return "\n".join(lines)


def parse_stage2_text(text: str) -> McqOcrResult:
    """Parse and validate local Stage2 OCR without calling another model."""
    lines = [line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and _QUESTION_OPENER.match(lines[0]):
        lines[0] = _QUESTION_OPENER.sub("", lines[0], count=1)

    options: list[tuple[str, list[str]]] = []
    stem_lines: list[str] = []
    current: tuple[str, list[str]] | None = None
    for line in lines:
        match = _OPTION_LINE.match(line)
        if match:
            current = (match.group(1), [match.group(2).strip()])
            options.append(current)
        elif current is None:
            stem_lines.append(line.strip())
        elif line.strip():
            current[1].append(line.strip())

    if not options:
        raise ValueError("missing choices A-D")
    labels = [label for label, _ in options]
    if labels != ["A", "B", "C", "D"]:
        raise ValueError(f"choices must be exactly A-D in order; got {labels}")
    stem = _join_ocr_lines(stem_lines)
    if not stem:
        raise ValueError("stem cannot be empty")
    choice_values = [_join_ocr_lines(parts) for _, parts in options]
    if any(not value for value in choice_values):
        raise ValueError("choice content cannot be empty")
    uncertain_tokens = sorted(set(re.findall(r"\S*\?\S*", text or "")))
    return McqOcrResult(
        stem=stem,
        choices=McqChoices(
            A=choice_values[0],
            B=choice_values[1],
            C=choice_values[2],
            D=choice_values[3],
        ),
        uncertain_tokens=uncertain_tokens,
    )


@runtime_checkable
class McqStructuredOcrClient(Protocol):
    def extract(self, *, prompt: str, image_path: Path) -> McqOcrResult: ...


class InstructorMcqOcrClient:
    """OpenAI-compatible Instructor client; separate from local Transformers generate()."""

    def __init__(
        self,
        *,
        provider: str,
        model_name: str,
        base_url: str | None = None,
        api_key_env: str | None = None,
        max_validation_retries: int = 1,
    ) -> None:
        if max_validation_retries not in {0, 1}:
            raise ValueError("max_validation_retries must be 0 or 1")
        self.provider = provider
        self.model_name = model_name
        self.base_url = (base_url or "").strip() or None
        self.api_key_env = (api_key_env or "").strip() or None
        self.max_validation_retries = max_validation_retries
        self._client: Any = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        import instructor

        kwargs: dict[str, object] = {"mode": instructor.Mode.JSON}
        if self.base_url is not None:
            kwargs["base_url"] = self.base_url
        if self.api_key_env is not None:
            api_key = os.environ.get(self.api_key_env)
            if api_key:
                kwargs["api_key"] = api_key
        from_provider = cast(Callable[..., Any], instructor.from_provider)
        self._client = from_provider(
            self.provider,
            async_client=False,
            **kwargs,
        )
        return self._client

    def extract(self, *, prompt: str, image_path: Path) -> McqOcrResult:
        import instructor

        client = self._get_client()
        response = client.create(
            model=self.model_name,
            response_model=McqOcrResult,
            max_retries=self.max_validation_retries,
            messages=[
                {
                    "role": "user",
                    "content": [
                        prompt.rstrip() + "\n\n" + _STRUCTURED_PROMPT_SUFFIX,
                        instructor.Image.from_path(image_path),
                    ],
                }
            ],
        )
        return McqOcrResult.model_validate(response)
