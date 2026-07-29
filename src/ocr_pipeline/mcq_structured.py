"""Structured Stage2 OCR for DSE Paper 2 MCQ crops."""

from __future__ import annotations

import os
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
