from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "homelab" / "ingest"))

from publish import publish  # noqa: E402


def test_publish_includes_figures(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "123.txt").write_text("hi", encoding="utf-8")
    figures = source / "figures"
    figures.mkdir()
    (figures / "p001_b012.png").write_bytes(b"PNG")
    share = tmp_path / "Z"
    (share / "jobs").mkdir(parents=True)

    final = publish(
        doc_id="123",
        source_dir=source,
        share_root=share,
        job_id="t-123",
    )

    assert (final / "figures" / "p001_b012.png").is_file()
    done = json.loads((final / "DONE.json").read_text(encoding="utf-8"))
    assert "figures/p001_b012.png" in {artifact["path"] for artifact in done["artifacts"]}
