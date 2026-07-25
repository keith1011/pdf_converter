"""Regression: booklet 2-up has a dark spine, not a white gutter."""

from pathlib import Path

from PIL import Image, ImageDraw

from ocr_pipeline.nup_classify import classify_nup
from ocr_pipeline.nup_types import NupClass


def _two_up_with_spine(path: Path, w: int = 400, h: int = 280) -> None:
    """Left/right content + dark spine in a pale mid gutter (booklet crease)."""
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, 160, 260], fill=(0, 0, 0))
    d.rectangle([240, 20, 380, 260], fill=(0, 0, 0))
    # pale gutter with thin dark crease
    d.rectangle([185, 0, 215, h], fill=(220, 220, 220))
    d.rectangle([w // 2 - 3, 0, w // 2 + 3, h], fill=(30, 30, 30))
    im.save(path)


def test_classify_two_up_with_dark_spine(tmp_path: Path):
    p = tmp_path / "spine.png"
    _two_up_with_spine(p)
    cls, conf = classify_nup(p)
    assert cls is NupClass.TWO_LR
    assert conf >= 0.55


def test_classify_real_2014_page2_if_present():
    page = Path("data/pdf_pages/2014-DSE-MATH-CP-2/page_002.png")
    if not page.is_file():
        return
    cls, conf = classify_nup(page)
    assert cls is NupClass.TWO_LR, f"got {cls} conf={conf}"
    assert conf >= 0.75


def test_classify_real_2014_page3_is_two_not_four():
    page = Path("data/pdf_pages/2014-DSE-MATH-CP-2/page_003.png")
    if not page.is_file():
        return
    cls, conf = classify_nup(page)
    assert cls is NupClass.TWO_LR, f"got {cls} conf={conf}"
    assert conf >= 0.75
