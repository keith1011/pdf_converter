from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ocr_pipeline.nup_router import decide_nup, read_nup_json, write_nup_json
from ocr_pipeline.nup_types import NupClass


def test_low_confidence_falls_back(tmp_path: Path):
    page = tmp_path / "page.png"
    Image.new("RGB", (20, 20), (255, 255, 255)).save(page)
    with patch("ocr_pipeline.nup_router.classify_nup", return_value=(NupClass.TWO_LR, 0.4)):
        d = decide_nup(page, 0, threshold=0.75, margin_norm=0.0, page_dir=tmp_path)
    assert d.fallback is True
    assert d.panels == []


def test_high_conf_two_splits_and_writes(tmp_path: Path):
    page = tmp_path / "page.png"
    Image.new("RGB", (200, 100), (255, 255, 255)).save(page)
    with patch("ocr_pipeline.nup_router.classify_nup", return_value=(NupClass.TWO_LR, 0.9)):
        d = decide_nup(page, 1, threshold=0.75, margin_norm=0.0, page_dir=tmp_path)
    assert d.fallback is False
    assert len(d.panels) == 2
    assert d.panels[0].path is not None and d.panels[0].path.exists()
    write_nup_json(tmp_path / "nup.json", d)
    loaded = read_nup_json(tmp_path / "nup.json")
    assert loaded.nup_class is NupClass.TWO_LR
    assert loaded.fallback is False


def test_disabled_forces_fallback(tmp_path: Path):
    page = tmp_path / "page.png"
    Image.new("RGB", (20, 20), (255, 255, 255)).save(page)
    d = decide_nup(
        page, 0, threshold=0.75, margin_norm=0.0, page_dir=tmp_path, enabled=False
    )
    assert d.fallback is True
    assert d.nup_class is NupClass.ONE
