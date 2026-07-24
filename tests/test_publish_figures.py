"""Publish includes figures/ in DONE artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from homelab.ingest.publish import publish


def test_publish_includes_figure_artifacts(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "demo.txt").write_text("(圖: 圓)\n", encoding="utf-8")
    pageir = {
        "pages": [
            {
                "page_index": 1,
                "segments": [
                    {
                        "kind": "figure",
                        "text": "圓",
                        "source_block_id": "p1_b0",
                        "bbox": [0, 0, 1, 1],
                        "integrity": "ok",
                        "crop_relpath": "figures/p1_b0.png",
                    }
                ],
            }
        ]
    }
    (src / "demo.pageir.json").write_text(json.dumps(pageir), encoding="utf-8")
    figs = src / "figures"
    figs.mkdir()
    (figs / "p1_b0.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")

    share = tmp_path / "share"
    share.mkdir()
    job = publish(doc_id="demo", source_dir=src, share_root=share, job_id="job-demo-fig")

    assert (job / "figures" / "p1_b0.png").is_file()
    done = json.loads((job / "DONE.json").read_text(encoding="utf-8"))
    paths = {a["path"] for a in done["artifacts"]}
    assert "demo.txt" in paths
    assert "demo.pageir.json" in paths
    assert "figures/p1_b0.png" in paths
