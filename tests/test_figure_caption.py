"""Tests for figure caption helper + FIGURE routing (mocked VLM, no GPU)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ocr_pipeline.content_first import finalize_content_first
from ocr_pipeline.figure_caption import caption_figure
from ocr_pipeline.models import (
    BBox,
    BlockType,
    ContentSegment,
    IntegrityStatus,
    LayoutBlock,
    SegmentKind,
)
from ocr_pipeline.routers import DynamicRouter, MathRouter, TextRouter


class _FakeVlm:
    def __init__(self, text: str = "直方圖顯示分數"):
        self.text = text
        self.calls: list[Path] = []

    def generate(self, prompt, *, image_path=None, max_new_tokens=None):
        if image_path is not None:
            self.calls.append(Path(image_path))
        return self.text


def test_caption_figure_strips_prefix(tmp_path: Path) -> None:
    png = tmp_path / "c.png"
    Image.new("RGB", (8, 8), color=(255, 0, 0)).save(png)
    vlm = _FakeVlm("圖：圓形圖")
    assert caption_figure(vlm, png) == "圓形圖"


def test_caption_figure_none_on_empty(tmp_path: Path) -> None:
    png = tmp_path / "c.png"
    Image.new("RGB", (4, 4)).save(png)
    assert caption_figure(_FakeVlm("   "), png) is None


def test_router_figure_writes_crop_and_caption(tmp_path: Path) -> None:
    page_img = tmp_path / "page.png"
    Image.new("RGB", (100, 100), color=(200, 200, 200)).save(page_img)
    crop_dir = tmp_path / "crops"
    figs_dir = tmp_path / "doc.figures"
    vlm = _FakeVlm("幾何圖形")
    router = DynamicRouter(
        MathRouter(),
        TextRouter(),
        crop_dir=crop_dir,
        figures_dir=figs_dir,
        vlm=vlm,
        skip_figures=False,
    )
    block = LayoutBlock(
        block_id="p1_b012",
        page=1,
        order=0,
        block_type=BlockType.FIGURE,
        bbox=BBox(10, 10, 50, 50),
        image_path=page_img,
    )
    out = router.route_block(block)
    assert out.meta.get("is_figure") is True
    assert out.meta.get("crop_relpath") == "figures/p1_b012.png"
    assert out.raw_text == "幾何圖形"
    assert (figs_dir / "p1_b012.png").is_file()


def test_router_skip_figures_still_skips(tmp_path: Path) -> None:
    page_img = tmp_path / "page.png"
    Image.new("RGB", (40, 40)).save(page_img)
    router = DynamicRouter(
        MathRouter(),
        TextRouter(),
        crop_dir=tmp_path / "crops",
        figures_dir=tmp_path / "figs",
        vlm=_FakeVlm(),
        skip_figures=True,
    )
    block = LayoutBlock(
        block_id="p1_b1",
        page=1,
        order=0,
        block_type=BlockType.FIGURE,
        bbox=BBox(0, 0, 20, 20),
        image_path=page_img,
    )
    out = router.route_block(block)
    assert out.meta.get("skipped") is True
    assert not out.meta.get("is_figure")


def test_finalize_merges_figure_segments(tmp_path: Path) -> None:
    fig = ContentSegment(
        kind=SegmentKind.FIGURE,
        text="圓形圖",
        source_block_id="p1_b0",
        bbox=BBox(1, 2, 3, 4),
        integrity=IntegrityStatus.OK,
        crop_relpath="figures/p1_b0.png",
    )
    full_txt, _tex, _t, _x, pageir, _w = finalize_content_first(
        source="demo",
        output_dir=tmp_path,
        page_drafts=[(1, "說明文字\n", BBox(0, 0, 10, 10))],
        wrap_tex_fn=lambda body: f"\\documentclass{{article}}\\begin{{document}}\n{body}\n\\end{{document}}\n",
        figure_segments_by_page={1: [fig]},
    )
    assert "(圖: 圓形圖)" in full_txt
    import json

    data = json.loads(pageir.read_text(encoding="utf-8"))
    kinds = [s["kind"] for s in data["pages"][0]["segments"]]
    assert "figure" in kinds
    fig_seg = next(s for s in data["pages"][0]["segments"] if s["kind"] == "figure")
    assert fig_seg["crop_relpath"] == "figures/p1_b0.png"
