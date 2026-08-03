from __future__ import annotations

from pathlib import Path

from ocr_pipeline.batch_export import run_batch


def test_batch_continues_after_one_failure(tmp_path: Path, monkeypatch):
    calls: list[str] = []

    def fake_stage(*, doc_id, output_dir, staging_dir):
        calls.append(f"stage:{doc_id}")
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / f"{doc_id}.txt").write_text("x", encoding="utf-8")
        return staging_dir

    def fake_publish(**kwargs):
        doc_id = kwargs["doc_id"]
        calls.append(f"publish:{doc_id}")
        if doc_id == "bad":
            raise RuntimeError("boom")
        return tmp_path / "jobs" / doc_id

    def fake_ingest(job_dir, **kwargs):
        calls.append(f"ingest:{job_dir.name}")
        return 1, 1

    monkeypatch.setattr("ocr_pipeline.batch_export.stage_job_dir", fake_stage)
    monkeypatch.setattr("ocr_pipeline.batch_export.publish", fake_publish)
    monkeypatch.setattr("ocr_pipeline.batch_export.ingest_job", fake_ingest)

    rc = run_batch(
        doc_ids=["bad", "good"],
        output_dir=tmp_path / "output",
        share_root=tmp_path / "Z",
        do_publish=True,
        do_ingest=True,
        fail_fast=False,
        staging_root=tmp_path / "staging",
        qdrant_url="http://example",
        api_key="k",
        reindex=False,
    )
    assert rc == 1
    assert calls == [
        "stage:bad",
        "publish:bad",
        "stage:good",
        "publish:good",
        "ingest:good",
    ]


def test_batch_continues_after_ingest_systemexit(tmp_path: Path, monkeypatch):
    calls: list[str] = []

    def fake_stage(*, doc_id, output_dir, staging_dir):
        calls.append(f"stage:{doc_id}")
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / f"{doc_id}.txt").write_text("x", encoding="utf-8")
        return staging_dir

    def fake_publish(**kwargs):
        doc_id = kwargs["doc_id"]
        calls.append(f"publish:{doc_id}")
        return tmp_path / "jobs" / doc_id

    def fake_ingest(job_dir, **kwargs):
        calls.append(f"ingest:{job_dir.name}")
        if job_dir.name == "first":
            raise SystemExit("no segments")
        return 1, 1

    monkeypatch.setattr("ocr_pipeline.batch_export.stage_job_dir", fake_stage)
    monkeypatch.setattr("ocr_pipeline.batch_export.publish", fake_publish)
    monkeypatch.setattr("ocr_pipeline.batch_export.ingest_job", fake_ingest)

    rc = run_batch(
        doc_ids=["first", "second"],
        output_dir=tmp_path / "output",
        share_root=tmp_path / "Z",
        do_publish=True,
        do_ingest=True,
        fail_fast=False,
        staging_root=tmp_path / "staging",
        qdrant_url="http://example",
        api_key="k",
        reindex=False,
    )
    assert rc == 1
    assert calls == [
        "stage:first",
        "publish:first",
        "ingest:first",
        "stage:second",
        "publish:second",
        "ingest:second",
    ]
