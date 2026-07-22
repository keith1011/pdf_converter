"""TDD T1: PageIR / ContentSegment models for content-first pipeline."""

from __future__ import annotations

from ocr_pipeline.models import BBox, ContentSegment, IntegrityStatus, PageIR, SegmentKind


def test_content_segment_math_stores_body_and_page_level_source():
    seg = ContentSegment(
        kind=SegmentKind.MATH,
        text=r"\frac{1}{2}",
        source_block_id="p1_stitched",
        bbox=BBox(0, 0, 100, 200),
        integrity=IntegrityStatus.OK,
    )
    assert seg.kind is SegmentKind.MATH
    assert seg.text == r"\frac{1}{2}"
    assert seg.source_block_id == "p1_stitched"
    assert seg.bbox.as_int_tuple() == (0, 0, 100, 200)
    assert seg.integrity is IntegrityStatus.OK


def test_page_ir_holds_ordered_segments():
    page = PageIR(
        page_index=1,
        segments=[
            ContentSegment(
                kind=SegmentKind.PROSE,
                text="設 x 為得分。",
                source_block_id="p1_stitched",
                bbox=BBox(0, 0, 100, 200),
            ),
            ContentSegment(
                kind=SegmentKind.MATH,
                text=r"x=60",
                source_block_id="p1_stitched",
                bbox=BBox(0, 0, 100, 200),
            ),
            ContentSegment(
                kind=SegmentKind.MARK_NOTE,
                text="1M+1A",
                source_block_id="p1_stitched",
                bbox=BBox(0, 0, 100, 200),
            ),
        ],
    )
    assert page.page_index == 1
    assert [s.kind for s in page.segments] == [
        SegmentKind.PROSE,
        SegmentKind.MATH,
        SegmentKind.MARK_NOTE,
    ]


def test_integrity_status_includes_repaired_and_fail():
    assert IntegrityStatus.REPAIRED.value == "repaired"
    assert IntegrityStatus.FAIL.value == "fail"
