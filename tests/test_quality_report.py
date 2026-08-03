"""TDD: Layer B quality report thresholds."""

from __future__ import annotations

from ocr_pipeline.quality import build_quality_report, write_quality_json


def _pageir(segments: list[dict]) -> dict:
    return {"pages": [{"page_index": 1, "segments": segments}]}


def test_empty_pageir_fails():
    report = build_quality_report(_pageir([]), doc_id="empty")
    assert report["verdict"] == "fail"
    assert "n_segments<1" in report["fail_reasons"]


def test_good_doc_passes():
    segs = [
        {"kind": "prose", "text": "這是一段夠長的試題題幹內容可以做向量檢索用途"},
        {"kind": "math", "text": r"\frac{a}{b}=c"},
        {"kind": "prose", "text": "另一段散文選項說明也要夠長才算合格片段內容"},
    ]
    report = build_quality_report(_pageir(segs), doc_id="good")
    assert report["verdict"] == "pass"
    assert report["fail_reasons"] == []
    assert report["pct_admitted_est"] == 1.0


def test_atomized_doc_fails_le3_and_ge20():
    # Mostly shreds → high pct_le3, low pct_ge20
    segs = [{"kind": "prose", "text": "("}] * 8 + [
        {"kind": "prose", "text": "一"},
        {"kind": "prose", "text": "這段稍長一點點但還不夠二十字"},
    ]
    report = build_quality_report(_pageir(segs), doc_id="bad")
    assert report["verdict"] == "fail"
    assert "pct_le3>0.20" in report["fail_reasons"]
    assert "pct_ge20<0.35" in report["fail_reasons"]


def test_write_quality_json(tmp_path):
    report = build_quality_report(
        [{"kind": "prose", "text": "這是一段夠長的試題題幹內容可以檢索"}],
        doc_id="x",
    )
    path = tmp_path / "x.quality.json"
    write_quality_json(path, report)
    assert path.is_file()
    assert "quality_schema" in path.read_text(encoding="utf-8")
