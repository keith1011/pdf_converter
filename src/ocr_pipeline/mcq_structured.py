"""Structured Stage2 OCR for DSE Paper 2 MCQ crops."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal, Protocol, cast, runtime_checkable

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
_IMAGE_CHOICE_PLACEHOLDER = "[圖像選項，見原題 crop]"


class _PaddleHtmlExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.image_count = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag.lower() == "img":
            self.image_count += 1

    def handle_data(self, data: str) -> None:
        self.text_parts.extend(part.strip() for part in data.splitlines() if part.strip())


def _normalize_paddle_image_choices(
    text: str,
) -> tuple[str, bool, str | None]:
    lower_text = text.lower()
    has_table = "<table" in lower_text
    if "<img" not in lower_text and not has_table:
        return text, False, None
    parser = _PaddleHtmlExtractor()
    parser.feed(text)
    if parser.image_count == 0:
        if has_table:
            return (
                "\n".join(parser.text_parts),
                True,
                "HTML table flattened to inline text",
            )
        return text, False, None
    labels = [
        match.group(1)
        for part in parser.text_parts
        if (match := _OPTION_LINE.fullmatch(part)) and not match.group(2).strip()
    ]
    if labels == ["A", "B", "C", "D"] and parser.image_count >= 4:
        first_option = next(
            i for i, part in enumerate(parser.text_parts) if _OPTION_LINE.fullmatch(part)
        )
        option_tail = parser.text_parts[first_option:]
        if all(_OPTION_LINE.fullmatch(part) for part in option_tail):
            stem_parts = [
                part
                for part in parser.text_parts[:first_option]
                if not _QUESTION_OPENER.fullmatch(part)
            ]
            stem = _join_ocr_lines(stem_parts)
            if stem:
                normalized = [stem]
                normalized.extend(
                    f"{label}. {_IMAGE_CHOICE_PLACEHOLDER}"
                    for label in ("A", "B", "C", "D")
                )
                return (
                    "\n".join(normalized),
                    True,
                    "image-only choices retained in question crop",
                )
    if (
        len(parser.text_parts) >= 5
        and not any(_OPTION_LINE.match(part) for part in parser.text_parts)
    ):
        stem = _join_ocr_lines(parser.text_parts[:-4])
        choices = parser.text_parts[-4:]
        if stem and all(choice.strip() for choice in choices):
            normalized = [stem]
            normalized.extend(
                f"{label}. {_join_ocr_lines([choice])}"
                for label, choice in zip(("A", "B", "C", "D"), choices, strict=True)
            )
            return (
                "\n".join(normalized),
                True,
                "unlabelled image choices assigned A-D by visual order",
            )
    return (
        "\n".join(parser.text_parts),
        True,
        "figures retained in question crop",
    )

def _join_ocr_lines(parts: list[str]) -> str:
    """join PDF layout lines into one natural sentence."""
    text = " ".join(part.strip() for part in parts if part.strip())

        # 中文標點前面不要有空格
    text = re.sub(r"\s+([，。；：！？、）】」』])", r"\1", text)

        # 中文標點或左括號後面不要有空格
    text = re.sub(r"([，。；：！？、（【「『])\s+", r"\1", text)

    return text.strip()
class OcrSpan(BaseModel):
    """One continuous text or mathematical fragment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["text", "math"]
    content: str = Field(min_length=1)

class McqSpanChoices(BaseModel):
    """A-D choices represented as text/math spans."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    A: list[OcrSpan] = Field(min_length=1)
    B: list[OcrSpan] = Field(min_length=1)
    C: list[OcrSpan] = Field(min_length=1)
    D: list[OcrSpan] = Field(min_length=1)


class McqSpanOcrResult(BaseModel):
    """One MCQ represented entirely by text/math spans."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stem: list[OcrSpan] = Field(min_length=1)
    choices: McqSpanChoices

def render_spans(spans: list[OcrSpan]) -> str:
    """Render text/math spans into one normalized line."""
    pieces: list[str] = []

    for span in spans:
        content = re.sub(r"\s+", " ", span.content).strip()

        if span.kind == "math":
            # Schema 中的 math content 不應包含 $。
            content = content.strip("$").strip()
            pieces.append(f"${content}$")
        else:
            content = re.sub(r"(?<!\\)\$", r"\\$", content)
            pieces.append(content)

    text = " ".join(pieces)

    # 清除中文標點前後的不自然空格。
    text = re.sub(r"\s+([，。；：！？、）】」』])", r"\1", text)
    text = re.sub(r"([（【「『])\s+", r"\1", text)

    return text

def render_span_result(
    question_id: int,
    result: McqSpanOcrResult,
) -> str:
    """Render one question as one stem line plus four choice lines."""

    choices = result.choices
    stem = render_spans(result.stem)
    stem = re.sub(rf"^{int(question_id)}\s*[.．]\s*", "", stem)

    return "\n".join(
        [
            f"{int(question_id)}. {stem}",
            f"A. {render_spans(choices.A)}",
            f"B. {render_spans(choices.B)}",
            f"C. {render_spans(choices.C)}",
            f"D. {render_spans(choices.D)}",
        ]
    )

def parse_span_json(text: str) -> McqSpanOcrResult:
    """Parse Qwen-VL JSON output into validated text/math spans."""
    content = (text or "").strip()

    # 容許模型意外加入 ```json ... ```
    content = re.sub(
        r"^```(?:json)?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(r"\s*```$", "", content)

    # 只保留第一個 { 至最後一個 }
    start = content.find("{")
    end = content.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError("structured OCR output does not contain JSON")

    return McqSpanOcrResult.model_validate_json(
        content[start : end + 1]
    )

def render_span_json(question_number: int, raw: str) -> str:
    result = parse_span_json(raw)
    return render_span_result(question_number, result)

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
    normalized_text, has_images, image_warning = _normalize_paddle_image_choices(
        text or ""
    )
    lines = [
        line.rstrip()
        for line in normalized_text.replace("\r\n", "\n").split("\n")
    ]
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
        warnings=[image_warning] if image_warning else [],
        requires_review=has_images,
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
