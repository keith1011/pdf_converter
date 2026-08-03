"""DynamicRouter skip_figures + figure routing."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.routers import DynamicRouter, MathRouter, TextRouter


class _TextEngine:
    def ocr(self, crop_path: Path) -> str:
        return f"caption:{crop_path.name}"


def _page_and_router(tmp_path: Path, *, skip_figures: bool):
    page = tmp_path / "page.png"
    Image.new("RGB", (40, 40), color=(255, 255, 255)).save(page)
    router = DynamicRouter(
        MathRouter(formula_engine=type("F", (), {"ocr": staticmethod(lambda p: "$$x$$")})()),
        TextRouter(text_engine=_TextEngine(), table_engine=_TextEngine()),
        crop_dir=tmp_path / "crops",
        skip_figures=skip_figures,
    )
    return router, page


def test_skip_figures_true_crops_but_does_not_ocr(tmp_path):
    router, page = _page_and_router(tmp_path, skip_figures=True)
    block = LayoutBlock("b0", BlockType.FIGURE, BBox(2, 2, 20, 20), 0, 1, page, meta={})
    out = router.route_block(block)
    assert out.raw_text == ""
    assert out.meta.get("skipped") is True
    assert out.meta.get("skip_reason") == "skip_figures"
    assert out.crop_path is not None
    assert out.crop_path.exists()


def test_skip_figures_false_routes_figure_via_text_engine(tmp_path):
    router, page = _page_and_router(tmp_path, skip_figures=False)
    block = LayoutBlock("b1", BlockType.FIGURE, BBox(2, 2, 20, 20), 0, 1, page, meta={})
    out = router.route_block(block)
    assert out.crop_path is not None
    assert out.crop_path.exists()
    assert out.raw_text == "caption:b1.png"
    assert out.meta.get("skipped") is not True
