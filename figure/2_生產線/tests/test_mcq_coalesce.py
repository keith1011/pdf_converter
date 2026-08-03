"""MCQ fragment coalesce for stitch + segmenter."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.assemble import DraftAssembler, coalesce_stitched_fragments
from ocr_pipeline.models import BBox, BlockType, LayoutBlock, SegmentKind
from ocr_pipeline.prompts import CONTENT_FIRST_POLISH_PROMPT, TEXT_ROUTER_PROMPT
from ocr_pipeline.segmenter import coalesce_mcq_segments, segment_stitched_page


def test_coalesce_stitched_glues_option_letter_value_punct():
    text = coalesce_stitched_fragments(["A.", "-1", "。", "B.", "2", "。"])
    assert "A. -1。" in text
    assert "B. 2。" in text
    assert text.count("\n\n") == 1


def test_draft_assembler_uses_coalesce():
    blocks = [
        LayoutBlock(
            block_id="p1_b0",
            block_type=BlockType.TEXT,
            bbox=BBox(0, 0, 10, 10),
            order=0,
            page=1,
            image_path=Path("p.png"),
            raw_text="A.",
        ),
        LayoutBlock(
            block_id="p1_b1",
            block_type=BlockType.EQUATION,
            bbox=BBox(0, 10, 10, 20),
            order=1,
            page=1,
            image_path=Path("p.png"),
            raw_text="-4",
        ),
        LayoutBlock(
            block_id="p1_b2",
            block_type=BlockType.TEXT,
            bbox=BBox(0, 20, 10, 30),
            order=2,
            page=1,
            image_path=Path("p.png"),
            raw_text="。",
        ),
    ]
    assert DraftAssembler().stitch(blocks) == "A. -4。"


def test_segmenter_coalesces_option_fragments():
    page = segment_stitched_page(
        page_index=1,
        stitched_text="A.\n-1\n。\nB.\n2\n。",
        page_bbox=BBox(0, 0, 10, 10),
    )
    texts = [s.text for s in page.segments]
    assert any("A." in t and "-1" in t for t in texts)
    assert any("B." in t and "2" in t for t in texts)
    assert "A." not in texts  # bare letter-only gone


def test_coalesce_mcq_segments_unit():
    from ocr_pipeline.models import ContentSegment, IntegrityStatus

    segs = [
        ContentSegment(
            kind=SegmentKind.PROSE,
            text="A.",
            source_block_id="p1",
            bbox=BBox(0, 0, 1, 1),
            integrity=IntegrityStatus.OK,
        ),
        ContentSegment(
            kind=SegmentKind.MATH,
            text="x=1",
            source_block_id="p1",
            bbox=BBox(0, 0, 1, 1),
            integrity=IntegrityStatus.OK,
        ),
    ]
    out = coalesce_mcq_segments(segs)
    assert len(out) == 1
    assert out[0].kind is SegmentKind.PROSE
    assert "A." in out[0].text and "x=1" in out[0].text


def test_prompts_ask_for_mcq_structure_and_no_fabricate():
    assert "選擇題" in TEXT_ROUTER_PROMPT or "選項" in TEXT_ROUTER_PROMPT
    assert "禁止" in TEXT_ROUTER_PROMPT or "不要" in TEXT_ROUTER_PROMPT
    assert "選項" in CONTENT_FIRST_POLISH_PROMPT
    assert "合併" in CONTENT_FIRST_POLISH_PROMPT or "同行" in CONTENT_FIRST_POLISH_PROMPT
