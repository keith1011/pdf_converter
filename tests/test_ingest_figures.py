# tests/test_ingest_figures.py
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "homelab" / "ingest"))

from ingest import CHUNK_VERSION, load_segments  # noqa: E402


def test_chunk_version_is_pageir_v2():
    assert CHUNK_VERSION == "pageir_v2"


def test_load_segments_includes_crop_path(tmp_path: Path):
    doc_id = "123"
    pageir = {
        "pages": [
            {
                "page_index": 1,
                "segments": [
                    {
                        "kind": "figure",
                        "text": "圓形示意圖",
                        "source_block_id": "p001_b012",
                        "bbox": [0, 0, 1, 1],
                        "integrity": "ok",
                        "crop_relpath": "figures/p001_b012.png",
                    }
                ],
            }
        ]
    }
    (tmp_path / f"{doc_id}.pageir.json").write_text(
        json.dumps(pageir), encoding="utf-8"
    )
    (tmp_path / f"{doc_id}.txt").write_text("x", encoding="utf-8")
    segs = load_segments(tmp_path, doc_id)
    assert segs[0]["kind"] == "figure"
    assert segs[0]["text"] == "圓形示意圖"
    assert segs[0]["crop_path"] == "figures/p001_b012.png"
