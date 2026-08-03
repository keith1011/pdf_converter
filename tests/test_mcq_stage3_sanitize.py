"""MCQ Stage2 prompt + Stage3 sanitize (keep crop text)."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.content_first import render_page_ir
from ocr_pipeline.models import (
    BBox,
    BlockType,
    ContentSegment,
    IntegrityStatus,
    LayoutBlock,
    PageIR,
    SegmentKind,
)
from ocr_pipeline.prompts import (
    MCQ_POLISH_PROMPT,
    MCQ_ROUTER_PROMPT,
    TEXT_ROUTER_PROMPT,
)
from ocr_pipeline.routers import TextRouter
from ocr_pipeline.segmenter import coalesce_mcq_segments


def test_mcq_router_prompt_forbids_solving_requires_options():
    p = MCQ_ROUTER_PROMPT
    assert "不要解題" in p or "禁止解題" in p
    assert "A" in p and "D" in p
    # Qwen3-VL: keep short (cookbook-style); do not dump full LATEX_MATH_RULES sheet
    assert "分數：禁止" not in p
    assert len(p) < 500
    assert MCQ_ROUTER_PROMPT != TEXT_ROUTER_PROMPT


def test_mcq_polish_prompt_forbids_solving():
    p = MCQ_POLISH_PROMPT
    assert "禁止解題" in p
    assert "A–D" in p or "A-D" in p or "選項" in p
    assert "<<<TXT>>>" in p and "<<<TEX>>>" in p


def test_split_question_chunks_keeps_options_despite_inner_blank_lines():
    from ocr_pipeline.assemble import split_question_chunks

    draft = (
        "1. $(x+1)=$\n\nA. $1$\n\nB. $2$\n\nC. $3$\n\nD. $4$\n\n"
        "2. stem two\n\nA. 1\n\nB. 2\n\nC. 3\n\nD. 4"
    )
    chunks = split_question_chunks(draft)
    assert len(chunks) == 2
    assert "A. $1$" in chunks[0] and "D. $4$" in chunks[0]
    assert chunks[1].startswith("2.")
    assert "A. 1" in chunks[1]


def test_mcq_sanitize_skips_vlm_and_keeps_stage2():
    class BoomVlm:
        def generate(self, prompt, image_path=None, *, max_new_tokens=None):
            raise AssertionError("MCQ sanitize must not call VLM")

    draft = (
        "1. $(x+1)(x^2+x+1)=$\nA. $x^3+1$\nB. $x^3+x$\nC. $x^3+2x$\nD. $x^3$\n\n"
        "2. stem two\nA. 1\nB. 2\nC. 3\nD. 4"
    )
    txt, tex, warn = FinalPolisher(BoomVlm(), mcq_stage3="sanitize").polish(draft)
    assert any("sanitize" in w for w in warn)
    assert "1." in txt and "2." in txt
    assert "\n\n" in txt
    assert "A. $x^3+1$" in txt
    assert "故" not in txt
    body = FinalPolisher.extract_tex_body(tex)
    assert "1." in body and "2." in body


def test_polish_mcq_single_question_page_skips_vlm():
    class BoomVlm:
        def generate(self, *a, **k):
            raise AssertionError("polish_mcq sanitize must not call VLM")

    draft = "5. 若 $n=$ \nA. 1\nB. 2\nC. 3\nD. 4"
    txt, tex, warn = FinalPolisher(BoomVlm(), mcq_stage3="sanitize").polish_mcq(draft)
    assert "5." in txt and "A. 1" in txt
    assert any("sanitize" in w for w in warn)


def test_mcq_vlm_mode_uses_mcq_prompt():
    seen: list[str] = []

    class FakeVlm:
        def generate(self, prompt, image_path=None, *, max_new_tokens=None):
            seen.append(prompt)
            draft = prompt.split("草稿：", 1)[-1].strip()
            return (
                f"<<<TXT>>>\n{draft}\n<<<TEX>>>\n"
                f"\\documentclass{{ctexart}}\\begin{{document}}\n{draft}\n\\end{{document}}"
            )

    draft = "1. stem\nA. 1\nB. 2\nC. 3\nD. 4\n\n2. stem2\nA. 1\nB. 2\nC. 3\nD. 4"
    FinalPolisher(FakeVlm(), mcq_stage3="vlm").polish(draft)
    assert len(seen) == 2
    assert all("禁止解題" in p for p in seen)


def test_text_router_uses_mcq_prompt_for_question_id():
    calls: list[str] = []

    class FakeEngine:
        def ocr(self, crop_path, *, prompt=None):
            calls.append(prompt or "")
            return "1. ok\nA. 1\nB. 2\nC. 3\nD. 4"

    block = LayoutBlock(
        block_id="p002_q001",
        block_type=BlockType.TEXT,
        bbox=BBox(0, 0, 10, 10),
        order=0,
        page=2,
        image_path=Path("x.png"),
        crop_path=Path("x.png"),
        meta={"question_id": 1},
    )
    TextRouter(text_engine=FakeEngine()).process(block)
    assert calls and ("不要解題" in calls[0] or "禁止解題" in calls[0])
    assert "A B C D" in calls[0] or "選項" in calls[0]
    assert r"\$" in calls[0]
    assert "貨幣" in calls[0]


def test_render_inserts_blank_line_before_question_openers():
    page = PageIR(
        page_index=2,
        segments=[
            ContentSegment(
                kind=SegmentKind.PROSE,
                text="1. stem one",
                source_block_id="p2",
                bbox=BBox(0, 0, 1, 1),
                integrity=IntegrityStatus.OK,
            ),
            ContentSegment(
                kind=SegmentKind.PROSE,
                text="A. 1",
                source_block_id="p2",
                bbox=BBox(0, 0, 1, 1),
                integrity=IntegrityStatus.OK,
            ),
            ContentSegment(
                kind=SegmentKind.PROSE,
                text="2. stem two",
                source_block_id="p2",
                bbox=BBox(0, 0, 1, 1),
                integrity=IntegrityStatus.OK,
            ),
        ],
    )
    txt, _ = render_page_ir(page)
    assert "\n\n2." in txt.replace("\r\n", "\n")


def test_coalesce_does_not_glue_next_question_onto_option():
    segs = [
        ContentSegment(
            kind=SegmentKind.PROSE,
            text="A. $x+1$",
            source_block_id="p",
            bbox=BBox(0, 0, 1, 1),
            integrity=IntegrityStatus.OK,
        ),
        ContentSegment(
            kind=SegmentKind.PROSE,
            text="2. next stem",
            source_block_id="p",
            bbox=BBox(0, 0, 1, 1),
            integrity=IntegrityStatus.OK,
        ),
    ]
    out = coalesce_mcq_segments(segs)
    assert len(out) == 2
    assert out[1].text.startswith("2.")
