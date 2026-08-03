"""TDD: ingest quality gate decisions (no Qdrant)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "homelab" / "ingest"))

from ingest import (  # noqa: E402
    filter_admitted_segments,
    load_quality_report,
    should_refuse_ingest,
)

from ocr_pipeline.quality import build_quality_report, write_quality_json  # noqa: E402


def test_filter_admitted_drops_shreds():
    segs = [
        {"kind": "prose", "text": "("},
        {"kind": "prose", "text": "這是一段夠長的試題題幹內容可以做向量檢索用途"},
        {"kind": "math", "text": "x=1"},
    ]
    kept, dropped = filter_admitted_segments(segs)
    assert len(kept) == 1
    assert len(dropped) == 2


def test_refuse_fail_when_require_pass():
    report = {"verdict": "fail", "fail_reasons": ["pct_le3>0.20"]}
    reason = should_refuse_ingest(
        report, require_pass=True, ingest_partial=False, force_ingest=False
    )
    assert reason is not None
    assert "fail" in reason.lower() or "quality" in reason.lower()


def test_partial_allows_fail():
    report = {"verdict": "fail", "fail_reasons": ["pct_le3>0.20"]}
    assert (
        should_refuse_ingest(
            report, require_pass=True, ingest_partial=True, force_ingest=False
        )
        is None
    )


def test_force_allows_fail():
    report = {"verdict": "fail"}
    assert (
        should_refuse_ingest(
            report, require_pass=True, ingest_partial=False, force_ingest=True
        )
        is None
    )


def test_load_quality_report(tmp_path: Path):
    report = build_quality_report([], doc_id="d")
    write_quality_json(tmp_path / "d.quality.json", report)
    loaded = load_quality_report(tmp_path, "d")
    assert loaded is not None
    assert loaded["verdict"] == "fail"
