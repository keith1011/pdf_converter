"""T6: dual fixtures for content-first stitch → PageIR → render."""

from __future__ import annotations

import json
from pathlib import Path

from ocr_pipeline.content_first import apply_integrity_to_page, render_page_ir
from ocr_pipeline.models import BBox
from ocr_pipeline.segmenter import segment_stitched_page

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "content_first"
STITCH = FIXTURES / "stage2_stitch" / "sample_p1.txt"
PAGEIR_DIR = FIXTURES / "pageir"


def test_stage2_stitch_fixture_segments_and_renders_without_meta():
    draft = STITCH.read_text(encoding="utf-8")
    assert "將圖片" in draft  # fixture includes meta to strip

    page = segment_stitched_page(
        page_index=1,
        stitched_text=draft,
        page_bbox=BBox(0, 0, 1000, 1000),
    )
    page, _warns = apply_integrity_to_page(page)
    txt, tex_body = render_page_ir(page)

    assert "$x=60$" in txt
    assert "$x=60$" in tex_body
    assert "將圖片" not in txt
    assert "將圖片" not in tex_body


def test_pageir_fixture_dir_has_json_with_expected_keys():
    assert PAGEIR_DIR.is_dir()
    jsons = sorted(PAGEIR_DIR.glob("*.json"))
    assert jsons, "expected at least one pageir json fixture"

    data = json.loads(jsons[0].read_text(encoding="utf-8"))
    assert "pages" in data
    page0 = data["pages"][0]
    assert "page_index" in page0
    assert "segments" in page0
    seg0 = page0["segments"][0]
    for key in ("kind", "text", "source_block_id", "bbox", "integrity"):
        assert key in seg0
