from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.mcq_structured import (
    InstructorMcqOcrClient,
    McqChoices,
    McqOcrResult,
    parse_stage2_text,
    render_text,
)
from ocr_pipeline.models import BBox, BlockType, LayoutBlock, PageResult
from ocr_pipeline.pipeline import _write_questions_jsonl, check_mcq_coverage
from ocr_pipeline.routers import TextRouter
from ocr_pipeline.vlm_client import QwenVlClient, build_mcq_structured_client, build_vlm_client


def _result(**overrides) -> McqOcrResult:
    payload = {
        "stem": r"若 $x=1$，則",
        "choices": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "visible_figure_labels": [],
        "uncertain_tokens": [],
        "warnings": [],
        "requires_review": False,
    }
    payload.update(overrides)
    return McqOcrResult.model_validate(payload)


def _block(qid: int, *, text: str = "") -> LayoutBlock:
    return LayoutBlock(
        block_id=f"p002_q{qid:03d}",
        block_type=BlockType.TEXT,
        bbox=BBox(0, 0, 10, 10),
        order=qid - 1,
        page=2,
        image_path=Path("page.png"),
        crop_path=Path("crop.png"),
        raw_text=text,
        meta={"question_id": qid},
    )


def test_schema_requires_exactly_a_through_d():
    with pytest.raises(ValidationError):
        McqOcrResult(
            stem="stem",
            choices={"A": "1", "B": "2", "C": "3"},
        )

    with pytest.raises(ValidationError):
        McqOcrResult(
            stem="stem",
            choices={"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        )


def test_schema_does_not_accept_question_id_from_vlm():
    with pytest.raises(ValidationError):
        McqOcrResult.model_validate(
            {
                "question_id": 99,
                "stem": "stem",
                "choices": {"A": "1", "B": "2", "C": "3", "D": "4"},
            }
        )


def test_uncertain_token_forces_requires_review():
    result = _result(uncertain_tokens=["β?"])
    assert result.requires_review is True


def test_local_stage2_parser_validates_order_and_content():
    result = parse_stage2_text("1. stem\nA. one\nB. two\nC. three\nD. four")
    assert result.stem == "stem"
    assert list(result.choices.model_dump()) == ["A", "B", "C", "D"]


def test_local_stage2_parser_rejects_missing_or_misordered_choices():
    with pytest.raises(ValueError, match="exactly A-D"):
        parse_stage2_text("stem\nA. one\nC. three\nB. two\nD. four")
    with pytest.raises(ValueError, match="cannot be empty"):
        parse_stage2_text("stem\nA. one\nB. \nC. three\nD. four")


def test_local_stage2_parser_marks_uncertain_tokens_for_review():
    result = parse_stage2_text("stem ?\nA. one\nB. two\nC. three\nD. four")
    assert result.uncertain_tokens
    assert result.requires_review is True


def test_render_text_is_stable_and_uses_stage1_question_id():
    result = _result(visible_figure_labels=["O", "P"])
    expected = (
        "7. 若 $x=1$，則\n"
        "圖中標示：O、P\n"
        "A. 1\n"
        "B. 2\n"
        "C. 3\n"
        "D. 4"
    )
    assert render_text(7, result) == expected
    assert render_text(7, result) == expected


def test_general_pdf_router_does_not_call_structured_backend():
    class PlainEngine:
        def ocr(self, crop_path, *, prompt=None):
            return "ordinary text"

    class StructuredBackend:
        def extract(self, *, prompt, image_path):
            raise AssertionError("general PDF block must not use MCQ structured OCR")

    block = _block(1)
    block.meta = {}
    TextRouter(
        text_engine=PlainEngine(),
        structured_ocr_client=StructuredBackend(),
    ).process(block)
    assert block.raw_text == "ordinary text"
    assert "structured_ocr" not in block.meta


def test_mcq_shadow_mode_keeps_legacy_text_and_attaches_structured_result():
    class PlainEngine:
        def ocr(self, crop_path, *, prompt=None):
            return "legacy Stage2 text"

    class StructuredBackend:
        def extract(self, *, prompt, image_path):
            return _result()

    block = _block(12)
    TextRouter(
        text_engine=PlainEngine(),
        structured_ocr_client=StructuredBackend(),
        structured_ocr_shadow_mode=True,
    ).process(block)

    assert block.raw_text == "legacy Stage2 text"
    assert block.meta["structured_ocr"]["stem"] == r"若 $x=1$，則"
    assert "question_id" not in block.meta["structured_ocr"]


def test_mcq_non_shadow_render_uses_metadata_question_id():
    class PlainEngine:
        def ocr(self, crop_path, *, prompt=None):
            return "legacy Stage2 text"

    class StructuredBackend:
        def extract(self, *, prompt, image_path):
            return _result()

    block = _block(12)
    TextRouter(
        text_engine=PlainEngine(),
        structured_ocr_client=StructuredBackend(),
        structured_ocr_shadow_mode=False,
    ).process(block)

    assert block.raw_text.startswith("12. ")
    assert not block.raw_text.startswith("1. ")


def test_mcq_stage3_remains_deterministic_sanitize():
    class BoomVlm:
        def generate(self, *args, **kwargs):
            raise AssertionError("MCQ sanitize must not call VLM")

    draft = "1. stem\nA. 1\nB. 2\nC. 3\nD. 4"
    text, _, warnings = FinalPolisher(BoomVlm(), mcq_stage3="sanitize").polish_mcq(draft)
    assert text == draft
    assert any("sanitize" in warning for warning in warnings)


def test_questions_jsonl_keeps_text_and_adds_structured_ocr(tmp_path):
    block = _block(1, text="1. legacy\nA. 1\nB. 2\nC. 3\nD. 4")
    block.meta["structured_ocr"] = _result().model_dump(mode="json")
    page = PageResult(
        page=2,
        image_path=Path("page.png"),
        blocks=[block],
        txt=block.raw_text,
    )
    out = tmp_path / "questions.jsonl"

    assert _write_questions_jsonl(out, [page]) == 1
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["text"] == block.raw_text
    assert row["structured_ocr"]["choices"] == {"A": "1", "B": "2", "C": "3", "D": "4"}


def test_questions_jsonl_without_structured_data_is_backward_compatible(tmp_path):
    block = _block(1, text="1. legacy\nA. 1\nB. 2\nC. 3\nD. 4")
    page = PageResult(page=2, image_path=Path("page.png"), blocks=[block], txt=block.raw_text)
    out = tmp_path / "questions.jsonl"

    _write_questions_jsonl(out, [page])
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["text"] == block.raw_text
    assert row["structured_ocr"] is None


def test_q1_to_q45_coverage_check():
    pages = [
        PageResult(
            page=2 + ((qid - 1) // 4),
            image_path=Path("page.png"),
            blocks=[_block(qid)],
        )
        for qid in range(1, 46)
    ]
    coverage = check_mcq_coverage(pages)
    assert coverage["complete"] is True
    assert coverage["missing_qids"] == []
    assert coverage["duplicate_qids"] == []

    incomplete = check_mcq_coverage(pages[:-1])
    assert incomplete["complete"] is False
    assert incomplete["missing_qids"] == [45]


def test_instructor_backend_uses_from_provider_response_model_and_one_retry(
    monkeypatch, tmp_path
):
    import instructor

    calls: dict[str, object] = {}

    class FakeClient:
        def create(self, **kwargs):
            calls["create"] = kwargs
            return _result()

    def fake_from_provider(provider, **kwargs):
        calls["provider"] = provider
        calls["provider_kwargs"] = kwargs
        return FakeClient()

    monkeypatch.setattr(instructor, "from_provider", fake_from_provider)
    monkeypatch.setattr(instructor.Image, "from_path", lambda path: f"IMAGE:{path}")
    image = tmp_path / "q.png"
    image.write_bytes(b"png")
    client = InstructorMcqOcrClient(
        provider="openai/Qwen/Qwen3-VL-8B-Instruct",
        model_name="Qwen/Qwen3-VL-8B-Instruct",
        base_url="http://127.0.0.1:8000/v1",
        max_validation_retries=1,
    )

    result = client.extract(prompt="OCR this MCQ", image_path=image)

    assert result.choices == McqChoices(A="1", B="2", C="3", D="4")
    assert calls["provider"] == "openai/Qwen/Qwen3-VL-8B-Instruct"
    create = calls["create"]
    assert isinstance(create, dict)
    assert create["response_model"] is McqOcrResult
    assert create["max_retries"] == 1
    assert create["model"] == "Qwen/Qwen3-VL-8B-Instruct"


def test_instructor_backend_rejects_unbounded_retry_configuration():
    with pytest.raises(ValueError, match="0 or 1"):
        InstructorMcqOcrClient(
            provider="openai/model",
            model_name="model",
            max_validation_retries=2,
        )


def test_structured_backend_is_opt_in_and_transformers_qwen_remains_default():
    assert build_mcq_structured_client({}) is None
    client = build_vlm_client(
        {
            "vlm": {
                "backend": "qwen",
                "model_name": "Qwen/Qwen3-VL-8B-Instruct",
                "load_in_4bit": True,
            }
        }
    )
    assert isinstance(client, QwenVlClient)
    assert client.load_in_4bit is True

def test_local_mcq_validation_renders_stem_and_choices_as_five_lines():
    class PlainEngine:
        def ocr(self, crop_path, *, prompt=None):
            return (
                "設\n"
                "k\n"
                "為一常數。若\n"
                "f(x)=2x^{2}-5x+k，\n"
                "則\n"
                "$f(2)-f(-2)=$\n"
                "A. -20。\n"
                "B. 0。\n"
                "C. 16。\n"
                "D. 2k。"
            )

    block = _block(6)

    TextRouter(
        text_engine=PlainEngine(),
        local_mcq_validation_enabled=True,
    ).process(block)

    assert block.raw_text == (
        "6. 設 k 為一常數。若 f(x)=2x^{2}-5x+k，則 $f(2)-f(-2)=$\n"
        "A. -20。\n"
        "B. 0。\n"
        "C. 16。\n"
        "D. 2k。"
    )

    def test_parser_removes_layout_spaces_around_chinese_punctuation():
        raw = """設
                k
                為一常數。若
                f(x)=2x^{2}-5x+k，
                則
                $f(2)-f(-2)=$
                A. -20。
                B. 0。
                C. 16。
                D. 2k。"""

        result = parse_stage2_text(raw)

        assert result.stem == (
            "設 k 為一常數。若 f(x)=2x^{2}-5x+k，則 $f(2)-f(-2)=$"
    )