from pathlib import Path

from PIL import Image

from ocr_pipeline.nup_crop import crop_panels, fixed_panel_boxes
from ocr_pipeline.nup_types import NupClass, NupPanel


def test_fixed_panel_boxes_two_lr():
    boxes = fixed_panel_boxes(NupClass.TWO_LR)
    assert [v for v, _ in boxes] == ["v0", "v1"]
    assert boxes[0][1] == (0.0, 0.0, 0.5, 1.0)
    assert boxes[1][1] == (0.5, 0.0, 1.0, 1.0)


def test_fixed_panel_boxes_four_2x2():
    boxes = fixed_panel_boxes(NupClass.FOUR_2X2)
    assert [v for v, _ in boxes] == ["v0", "v1", "v2", "v3"]
    # v0 TL, v1 TR, v2 BL, v3 BR
    assert boxes[0][1] == (0.0, 0.0, 0.5, 0.5)
    assert boxes[3][1] == (0.5, 0.5, 1.0, 1.0)


def test_crop_panels_writes_pngs(tmp_path: Path):
    img_path = tmp_path / "page.png"
    Image.new("RGB", (200, 100), (255, 255, 255)).save(img_path)
    panels = [
        NupPanel("v0", (0.0, 0.0, 0.5, 1.0)),
        NupPanel("v1", (0.5, 0.0, 1.0, 1.0)),
    ]
    out = crop_panels(img_path, panels, tmp_path / "panels")
    assert out[0].path is not None and out[0].path.exists()
    assert Image.open(out[0].path).size == (100, 100)
    assert Image.open(out[1].path).size == (100, 100)
