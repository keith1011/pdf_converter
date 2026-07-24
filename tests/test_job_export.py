"""Tests for OCR → DONE staging / publish bridge (no Samba/Qdrant)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocr_pipeline.job_export import publish_and_ingest, stage_job_artifacts


def test_stage_renames_tagged_artifacts(tmp_path: Path) -> None:
    stem = "123.got-ppocr"
    (tmp_path / f"{stem}.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / f"{stem}.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n", encoding="utf-8")
    (tmp_path / f"{stem}.pageir.json").write_text('{"pages":[]}\n', encoding="utf-8")

    stage = stage_job_artifacts(output_dir=tmp_path, artifact_stem=stem, doc_id="123")
    assert stage == tmp_path / ".publish_stage" / "123"
    assert (stage / "123.txt").read_text(encoding="utf-8") == "hello\n"
    assert (stage / "123.tex").is_file()
    assert (stage / "123.pageir.json").is_file()
    # originals kept for scorecard
    assert (tmp_path / f"{stem}.txt").is_file()


def test_stage_requires_txt(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="required artifact"):
        stage_job_artifacts(output_dir=tmp_path, artifact_stem="missing", doc_id="123")


def test_stage_optional_tex_pageir(tmp_path: Path) -> None:
    (tmp_path / "abc.txt").write_text("only txt\n", encoding="utf-8")
    stage = stage_job_artifacts(output_dir=tmp_path, artifact_stem="abc", doc_id="abc")
    assert (stage / "abc.txt").is_file()
    assert not (stage / "abc.tex").exists()
    assert not (stage / "abc.pageir.json").exists()


def test_stage_copies_figures_and_checks_pageir(tmp_path: Path) -> None:
    stem = "123"
    (tmp_path / f"{stem}.txt").write_text("hi\n", encoding="utf-8")
    pageir = {
        "pages": [
            {
                "page_index": 1,
                "segments": [
                    {
                        "kind": "figure",
                        "text": "圓形圖",
                        "source_block_id": "p1_b0",
                        "bbox": [0, 0, 1, 1],
                        "integrity": "ok",
                        "crop_relpath": "figures/p1_b0.png",
                    }
                ],
            }
        ]
    }
    (tmp_path / f"{stem}.pageir.json").write_text(
        __import__("json").dumps(pageir), encoding="utf-8"
    )
    figs = tmp_path / f"{stem}.figures"
    figs.mkdir()
    (figs / "p1_b0.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")

    stage = stage_job_artifacts(output_dir=tmp_path, artifact_stem=stem, doc_id="123")
    assert (stage / "figures" / "p1_b0.png").is_file()


def test_stage_missing_listed_crop_fails(tmp_path: Path) -> None:
    stem = "123"
    (tmp_path / f"{stem}.txt").write_text("hi\n", encoding="utf-8")
    pageir = {
        "pages": [
            {
                "page_index": 1,
                "segments": [
                    {
                        "kind": "figure",
                        "text": "x",
                        "source_block_id": "p1_b0",
                        "bbox": [0, 0, 1, 1],
                        "integrity": "ok",
                        "crop_relpath": "figures/missing.png",
                    }
                ],
            }
        ]
    }
    (tmp_path / f"{stem}.pageir.json").write_text(
        __import__("json").dumps(pageir), encoding="utf-8"
    )
    with pytest.raises(FileNotFoundError, match="crop_relpath"):
        stage_job_artifacts(output_dir=tmp_path, artifact_stem=stem, doc_id="123")


def test_publish_and_ingest_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stem = "123.got-ppocr"
    (tmp_path / f"{stem}.txt").write_text("hi\n", encoding="utf-8")
    share = tmp_path / "share"
    share.mkdir()
    calls: list[str] = []

    def fake_publish(**kwargs):
        calls.append("publish")
        assert kwargs["doc_id"] == "123"
        assert (kwargs["source_dir"] / "123.txt").is_file()
        job = share / "jobs" / "job-123"
        job.mkdir(parents=True)
        return job

    def fake_ingest(job_dir, *, qdrant_url, api_key, reindex=False):
        calls.append("ingest")
        assert job_dir.name == "job-123"
        assert api_key == "writer-key"
        assert reindex is False
        return 3, 3

    monkeypatch.setenv("QDRANT_WRITER_KEY", "writer-key")
    import homelab.ingest.ingest as ingest_mod
    import homelab.ingest.publish as publish_mod

    monkeypatch.setattr(publish_mod, "publish", fake_publish)
    monkeypatch.setattr(ingest_mod, "ingest_job", fake_ingest)

    job_dir, upserted, total = publish_and_ingest(
        output_dir=tmp_path,
        artifact_stem=stem,
        doc_id="123",
        share_root=share,
        do_publish=True,
        do_ingest=True,
    )

    assert calls == ["publish", "ingest"]
    assert job_dir is not None and job_dir.name == "job-123"
    assert upserted == 3 and total == 3


def test_ingest_requires_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QDRANT_WRITER_KEY", raising=False)
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)
    job = tmp_path / "job"
    job.mkdir()
    with pytest.raises(SystemExit, match="QDRANT_WRITER_KEY"):
        publish_and_ingest(
            output_dir=tmp_path,
            artifact_stem="x",
            doc_id="x",
            share_root=tmp_path,
            do_publish=False,
            do_ingest=True,
            job_dir=job,
        )


def test_cli_publish_ingest_flags() -> None:
    from run_ocr_pipeline import build_parser

    p = build_parser({})
    args = p.parse_args(
        [
            "data/sources/123.pdf",
            "--publish",
            "--ingest",
            "--doc-id",
            "123",
            "--share-root",
            "Z:/",
            "--output-tag",
            "got-ppocr",
        ]
    )
    assert args.publish is True
    assert args.ingest is True
    assert args.doc_id == "123"
    assert args.output_tag == "got-ppocr"
    assert args.share_root == Path("Z:/")
