from ocr_pipeline.assemble import DraftAssembler
from ocr_pipeline.content_first import build_page_ir_from_stitched
from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from pathlib import Path


def test_stitch_markers_assign_version_id_on_segments():
    blocks = [
        LayoutBlock(
            block_id="a",
            block_type=BlockType.TEXT,
            bbox=BBox(0, 0, 1, 1),
            order=0,
            page=1,
            image_path=Path("p.png"),
            raw_text="Q16 left stem",
            meta={"version_id": "v0"},
        ),
        LayoutBlock(
            block_id="b",
            block_type=BlockType.TEXT,
            bbox=BBox(0, 0, 1, 1),
            order=1,
            page=1,
            image_path=Path("p.png"),
            raw_text="Q19 right stem",
            meta={"version_id": "v1"},
        ),
    ]
    draft = DraftAssembler().stitch(blocks)
    assert "<<<nup:v0>>>" in draft and "<<<nup:v1>>>" in draft
    page, _ = build_page_ir_from_stitched(1, draft, BBox(0, 0, 100, 100))
    vids = [s.version_id for s in page.segments]
    assert "v0" in vids and "v1" in vids
    assert page.segments[0].version_id == "v0"
    assert any(s.version_id == "v1" and "Q19" in s.text for s in page.segments)
