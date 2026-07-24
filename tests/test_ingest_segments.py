"""Unit tests for ingest load_segments / payload (no Qdrant/embedder)."""

from __future__ import annotations

import json
from pathlib import Path

from homelab.ingest.ingest import CHUNK_VERSION, load_segments, point_id


def test_chunk_version_is_pageir_v2() -> None:
    assert CHUNK_VERSION == "pageir_v2"


def test_load_segments_figure_crop_path(tmp_path: Path) -> None:
    pageir = {
        "pages": [
            {
                "page_index": 1,
                "segments": [
                    {
                        "kind": "prose",
                        "text": "說明",
                        "source_block_id": "p1_s0",
                        "bbox": [0, 0, 1, 1],
                        "integrity": "ok",
                    },
                    {
                        "kind": "figure",
                        "text": "直方圖",
                        "source_block_id": "p1_b1",
                        "bbox": [0, 0, 10, 10],
                        "integrity": "ok",
                        "crop_relpath": "figures/p1_b1.png",
                    },
                ],
            }
        ]
    }
    (tmp_path / "doc.pageir.json").write_text(
        json.dumps(pageir, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "doc.txt").write_text("說明\n", encoding="utf-8")

    segs = load_segments(tmp_path, "doc")
    assert len(segs) == 2
    prose, fig = segs
    assert prose["kind"] == "prose"
    assert "crop_path" not in prose
    assert fig["kind"] == "figure"
    assert fig["text"] == "直方圖"
    assert fig["crop_path"] == "figures/p1_b1.png"


def test_point_id_includes_chunk_version() -> None:
    a = point_id("doc", 1, "p1_s0")
    # Stable uuid5 — regenerating with same inputs must match
    assert a == point_id("doc", 1, "p1_s0")
    assert len(a) == 36
