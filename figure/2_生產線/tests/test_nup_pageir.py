import json
from pathlib import Path

from ocr_pipeline.content_first import apply_integrity_to_page, write_pageir_json
from ocr_pipeline.models import BBox, ContentSegment, IntegrityStatus, PageIR, SegmentKind


def test_pageir_json_includes_version_id(tmp_path: Path):
    page = PageIR(
        page_index=0,
        segments=[
            ContentSegment(
                kind=SegmentKind.PROSE,
                text="Q16 stem",
                source_block_id="p000_stitched",
                bbox=BBox(0, 0, 10, 10),
                version_id="v0",
            )
        ],
    )
    path = tmp_path / "pageir.json"
    write_pageir_json(path, [page])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["pages"][0]["segments"][0]["version_id"] == "v0"


def test_integrity_preserves_version_id():
    page = PageIR(
        page_index=0,
        segments=[
            ContentSegment(
                kind=SegmentKind.MATH,
                text="x+1",
                source_block_id="p0",
                bbox=BBox(0, 0, 1, 1),
                integrity=IntegrityStatus.OK,
                version_id="v1",
            )
        ],
    )
    out, _ = apply_integrity_to_page(page)
    assert out.segments[0].version_id == "v1"
