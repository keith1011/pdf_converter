from __future__ import annotations

from pathlib import Path

from PIL import Image

from ocr_pipeline.figure_export import export_figures
from ocr_pipeline.models import BBox, BlockType, LayoutBlock, SegmentKind


class FakeVlm:
    def generate(self, prompt, image_path=None, max_new_tokens=None):
        assert image_path is not None
        assert "圖" in prompt or "caption" in prompt.lower() or "說明" in prompt
        return "圓形面積示意圖"


def test_export_figures_writes_png_and_segment(tmp_path: Path):
    page = tmp_path / "page.png"
    Image.new("RGB", (40, 40), color=(200, 200, 200)).save(page)
    block = LayoutBlock(
        "p001_b012",
        BlockType.FIGURE,
        BBox(2, 2, 20, 20),
        0,
        1,
        page,
        crop_path=None,
    )
    figures_dir = tmp_path / "figures"
    segs, warns = export_figures(blocks=[block], figures_dir=figures_dir, vlm=FakeVlm())
    assert warns == []
    assert len(segs) == 1
    assert segs[0].kind is SegmentKind.FIGURE
    assert segs[0].text == "圓形面積示意圖"
    assert segs[0].crop_relpath == "figures/p001_b012.png"
    assert (figures_dir / "p001_b012.png").is_file()


class BoomVlm:
    def generate(self, prompt, image_path=None, max_new_tokens=None):
        raise RuntimeError("cuda boom")


def test_export_figures_skips_failed_caption(tmp_path: Path):
    page = tmp_path / "page.png"
    Image.new("RGB", (40, 40), color=(200, 200, 200)).save(page)
    block = LayoutBlock(
        "p001_b099",
        BlockType.FIGURE,
        BBox(2, 2, 20, 20),
        0,
        1,
        page,
    )
    segs, warns = export_figures(
        blocks=[block], figures_dir=tmp_path / "figures", vlm=BoomVlm()
    )
    assert segs == []
    assert any("p001_b099" in w for w in warns)
