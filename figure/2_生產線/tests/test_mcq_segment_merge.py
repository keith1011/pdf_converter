"""MCQ PageIR: merge one question into one segment for quality gate."""

from __future__ import annotations

import re

from ocr_pipeline.models import BBox, ContentSegment, IntegrityStatus, SegmentKind
from ocr_pipeline.quality import build_quality_report
from ocr_pipeline.segmenter import coalesce_mcq_segments, segment_stitched_page


def _seg(text: str, *, kind: SegmentKind = SegmentKind.PROSE) -> ContentSegment:
    return ContentSegment(
        kind=kind,
        text=text,
        source_block_id="p",
        bbox=BBox(0, 0, 1, 1),
        integrity=IntegrityStatus.OK,
    )


def test_coalesce_merges_full_mcq_into_one_segment_per_question():
    segs = [
        _seg("1."),
        _seg("(x+1)(x^2+x+1)=", kind=SegmentKind.MATH),
        _seg("A. $x^3+1$"),
        _seg("B. $(x+1)^3$"),
        _seg("C. $x^3+x^2+x+1$"),
        _seg("D. $x^3+2x^2+2x+1$"),
        _seg("2."),
        _seg("若"),
        _seg("p=1", kind=SegmentKind.MATH),
        _seg("則"),
        _seg("n="),
        _seg("A. 1"),
        _seg("B. 2"),
        _seg("C. 3"),
        _seg("D. 4"),
    ]
    out = coalesce_mcq_segments(segs)
    assert len(out) == 2
    assert out[0].kind is SegmentKind.PROSE
    assert out[0].text.startswith("1.")
    assert "A. $x^3+1$" in out[0].text and "D. $x^3+2x^2+2x+1$" in out[0].text
    assert out[1].text.startswith("2.")
    assert "若" in out[1].text and "A. 1" in out[1].text


def test_qid_not_swallowed_into_math_dollars():
    page = segment_stitched_page(
        page_index=3,
        stitched_text=(
            "3. 若 $p=1$，則 $n=$\nA. 1\nB. 2\nC. 3\nD. 4\n\n"
            "4. 0.0023456789 =\n"
            "A. 0.00235（準確至六位小數）。 B. 0.002345（準確至六位小數）。 "
            "C. 0.002346（準確至六位有效數字）。 D. 0.00234568（準確至六位有效數字）。\n"
        ),
        page_bbox=BBox(0, 0, 100, 100),
    )
    assert len(page.segments) == 2
    q4 = page.segments[1].text
    assert q4.startswith("4.")
    assert not q4.startswith("$4.")
    assert "$4." not in q4
    # Options each on their own line
    for letter in "ABCD":
        assert re.search(rf"(?m)^{letter}\.", q4), q4


def test_normalize_unwraps_wrapped_qid_and_splits_options():
    from ocr_pipeline.segmenter import normalize_mcq_block_text

    out = normalize_mcq_block_text(
        "$4. 0.0023456789 =$\nA. 1。 B. 2。 C. 3。 D. 4。"
    )
    assert out.startswith("4.")
    assert "$4." not in out
    assert re.search(r"(?m)^A\.", out)
    assert re.search(r"(?m)^B\.", out)
    assert re.search(r"(?m)^C\.", out)
    assert re.search(r"(?m)^D\.", out)


def test_segment_stitched_mcq_page_few_long_segments():
    draft = (
        "1. $(x+1)(x^{2}+x+1)=$\n"
        "A. $x^{3}+1$\n"
        "B. $(x+1)^{3}$\n"
        "C. $x^{3}+x^{2}+x+1$\n"
        "D. $x^{3}+2x^{2}+2x+1$\n\n"
        "2. 若 $p+3q=4$ 及 $5p+9q=2$，則 $p=$\n"
        "A. -5。\n"
        "B. -3。\n"
        "C. 3。\n"
        "D. 5。\n"
    )
    page = segment_stitched_page(
        page_index=2,
        stitched_text=draft,
        page_bbox=BBox(0, 0, 100, 100),
    )
    assert len(page.segments) == 2
    assert all(len(s.text) >= 20 for s in page.segments)
    assert all(s.kind is SegmentKind.PROSE for s in page.segments)

    payload = {
        "pages": [
            {
                "page_index": 2,
                "segments": [
                    {
                        "kind": s.kind.value,
                        "text": s.text,
                        "source_block_id": s.source_block_id,
                        "bbox": [0, 0, 1, 1],
                        "integrity": "ok",
                    }
                    for s in page.segments
                ],
            }
        ]
    }
    report = build_quality_report(payload, doc_id="mcq-merge")
    assert report["pct_le3"] <= 0.20
    assert report["pct_ge20"] >= 0.35
    assert report["verdict"] in {"pass", "warn"}


def test_non_mcq_page_still_keeps_math_separate():
    page = segment_stitched_page(
        page_index=1,
        stitched_text="設 x 為得分。\n$x=60$\n",
        page_bbox=BBox(0, 0, 10, 10),
    )
    kinds = [s.kind for s in page.segments]
    assert SegmentKind.MATH in kinds
    assert any(s.text == "x=60" for s in page.segments)
