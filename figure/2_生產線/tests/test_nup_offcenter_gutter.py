"""Off-center booklet gutter must still classify as 2-up."""

from pathlib import Path

from PIL import Image, ImageDraw

from ocr_pipeline.nup_classify import classify_nup, find_best_vertical_split
from ocr_pipeline.nup_crop import fixed_panel_boxes
from ocr_pipeline.nup_types import NupClass


def _two_up_off_center(path: Path, *, split_frac: float, w: int = 400, h: int = 280) -> None:
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    sx = int(w * split_frac)
    d.rectangle([15, 15, sx - 15, h - 15], fill=(0, 0, 0))
    d.rectangle([sx + 15, 15, w - 15, h - 15], fill=(0, 0, 0))
    d.rectangle([sx - 8, 0, sx + 8, h], fill=(210, 210, 210))
    d.rectangle([sx - 2, 0, sx + 2, h], fill=(25, 25, 25))
    im.save(path)


def test_find_best_vertical_split_off_center(tmp_path: Path):
    p = tmp_path / "off.png"
    _two_up_off_center(p, split_frac=0.42)
    score, x_norm = find_best_vertical_split(p)
    assert score >= 0.55
    assert 0.38 <= x_norm <= 0.46


def test_classify_off_center_gutter_as_two_lr(tmp_path: Path):
    p = tmp_path / "off55.png"
    _two_up_off_center(p, split_frac=0.55)
    cls, conf = classify_nup(p)
    assert cls is NupClass.TWO_LR
    assert conf >= 0.55


def test_fixed_panel_boxes_respect_split_x():
    boxes = fixed_panel_boxes(NupClass.TWO_LR, split_x=0.42)
    assert boxes[0][1][2] == 0.42  # v0 x2
    assert boxes[1][1][0] == 0.42  # v1 x1


def test_real_2014_missed_pages_are_two_lr():
    for i in (4, 6, 7):
        page = Path(f"1_收集資料/data/pdf_pages/2014-DSE-MATH-CP-2/page_{i:03d}.png")
        if not page.is_file():
            continue
        cls, conf = classify_nup(page)
        assert cls is NupClass.TWO_LR, f"p{i} got {cls} conf={conf}"
        assert conf >= 0.55, f"p{i} conf={conf}"
