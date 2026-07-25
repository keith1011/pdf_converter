from pathlib import Path

from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.nup_merge import merge_panel_blocks
from ocr_pipeline.nup_types import NupPanel


def test_merge_orders_versions_and_remaps():
    page_img = Path("page.png")
    v0 = NupPanel("v0", (0.0, 0.0, 0.5, 1.0))
    v1 = NupPanel("v1", (0.5, 0.0, 1.0, 1.0))
    b1 = LayoutBlock(
        block_id="tmp",
        block_type=BlockType.TEXT,
        bbox=BBox(10, 10, 30, 30),
        order=0,
        page=1,
        image_path=Path("v1.png"),
    )
    b0 = LayoutBlock(
        block_id="tmp",
        block_type=BlockType.TEXT,
        bbox=BBox(5, 5, 20, 20),
        order=0,
        page=1,
        image_path=Path("v0.png"),
    )
    merged = merge_panel_blocks(
        [(v0, [b0]), (v1, [b1])],
        page=1,
        page_image=page_img,
        page_w=200,
        page_h=100,
    )
    assert [m.meta["version_id"] for m in merged] == ["v0", "v1"]
    assert merged[1].bbox.x1 == 110.0
    assert merged[0].order == 0 and merged[1].order == 1
    assert merged[0].image_path == page_img
