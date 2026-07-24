"""Tests for batch_export CLI helpers (mocked publish_and_ingest)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocr_pipeline.batch_export import (
    resolve_artifact_stem,
    resolve_docs,
    run_batch,
)


def test_resolve_docs_dedupes_and_file(tmp_path: Path) -> None:
    f = tmp_path / "docs.txt"
    f.write_text("123\n# comment\n789\n123\n", encoding="utf-8")
    assert resolve_docs("123,456", f) == ["123", "456", "789"]


def test_resolve_artifact_stem_exact_and_tagged(tmp_path: Path) -> None:
    (tmp_path / "123.txt").write_text("a\n", encoding="utf-8")
    assert resolve_artifact_stem(tmp_path, "123") == "123"

    (tmp_path / "789.got-ppocr.txt").write_text("b\n", encoding="utf-8")
    assert resolve_artifact_stem(tmp_path, "789") == "789.got-ppocr"

    with pytest.raises(FileNotFoundError):
        resolve_artifact_stem(tmp_path, "missing")


def test_run_batch_continues_after_failure(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    calls: list[str] = []

    def fake(**kwargs):
        doc = kwargs["doc_id"]
        calls.append(doc)
        if doc == "a":
            raise RuntimeError("boom")
        return tmp_path / "job", 1, 1

    results = run_batch(
        doc_ids=["a", "b"],
        output_dir=tmp_path,
        share_root=tmp_path / "share",
        do_publish=True,
        do_ingest=False,
        reindex=False,
        fail_fast=False,
        publish_and_ingest_fn=fake,
    )
    assert calls == ["a", "b"]
    assert results[0][0] == "a" and results[0][1] is not None
    assert results[1] == ("b", None)


def test_run_batch_fail_fast(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    calls: list[str] = []

    def fake(**kwargs):
        calls.append(kwargs["doc_id"])
        raise RuntimeError("stop")

    results = run_batch(
        doc_ids=["a", "b"],
        output_dir=tmp_path,
        share_root=tmp_path / "share",
        do_publish=True,
        do_ingest=False,
        reindex=False,
        fail_fast=True,
        publish_and_ingest_fn=fake,
    )
    assert calls == ["a"]
    assert len(results) == 1
