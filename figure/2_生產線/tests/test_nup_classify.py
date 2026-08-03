from pathlib import Path

from PIL import Image, ImageDraw

from ocr_pipeline.nup_classify import classify_nup
from ocr_pipeline.nup_types import NupClass


def _two_column_page(path: Path, w: int = 200, h: int = 200) -> None:
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([10, 10, 85, 190], fill=(0, 0, 0))
    d.rectangle([115, 10, 190, 190], fill=(0, 0, 0))
    im.save(path)


def _single_column_page(path: Path, w: int = 200, h: int = 200) -> None:
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([40, 10, 160, 190], fill=(0, 0, 0))
    im.save(path)


def _four_quadrant_page(path: Path, w: int = 200, h: int = 200) -> None:
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([10, 10, 85, 85], fill=(0, 0, 0))
    d.rectangle([115, 10, 190, 85], fill=(0, 0, 0))
    d.rectangle([10, 115, 85, 190], fill=(0, 0, 0))
    d.rectangle([115, 115, 190, 190], fill=(0, 0, 0))
    im.save(path)


def test_classify_two_lr(tmp_path: Path):
    p = tmp_path / "two.png"
    _two_column_page(p)
    cls, conf = classify_nup(p)
    assert cls is NupClass.TWO_LR
    assert conf >= 0.75


def test_classify_single_not_two(tmp_path: Path):
    p = tmp_path / "one.png"
    _single_column_page(p)
    cls, conf = classify_nup(p)
    assert cls in (NupClass.ONE, NupClass.UNCERTAIN)
    assert not (cls is NupClass.TWO_LR and conf >= 0.75)


def test_classify_four_2x2(tmp_path: Path):
    p = tmp_path / "four.png"
    _four_quadrant_page(p)
    cls, conf = classify_nup(p)
    assert cls is NupClass.FOUR_2X2
    assert conf >= 0.75
