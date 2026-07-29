import json
from pathlib import Path

from ocr_pipeline.dse_mcq_ocr import load_ocr_lines_json


def test_load_ocr_lines_json(tmp_path: Path):
    p = tmp_path / "lines.json"
    p.write_text(
        json.dumps(
            {
                "page_width": 100,
                "page_height": 200,
                "lines": [{"text": "1. Hi", "bbox": [1, 2, 90, 20]}],
            }
        ),
        encoding="utf-8",
    )
    lines = load_ocr_lines_json(p)
    assert len(lines) == 1
    assert lines[0].text == "1. Hi"
    assert lines[0].page_width == 100
    assert lines[0].bbox == (1.0, 2.0, 90.0, 20.0)
