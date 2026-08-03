"""Unit tests for DONE.json validation (no Qdrant required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "homelab" / "ingest"))

from done import content_hash, sha256_file, validate_done_dict  # noqa: E402


def test_validate_done_ok(tmp_path: Path) -> None:
    txt = tmp_path / "123.txt"
    txt.write_text("hello\n", encoding="utf-8")
    digest = sha256_file(txt)
    data = {
        "done_schema": 1,
        "job_id": "20260723-123-001",
        "doc_id": "123",
        "created_at": "2026-07-23T00:00:00+00:00",
        "source_pdf": "123.pdf",
        "artifacts": [{"path": "123.txt", "sha256": digest}],
        "ocr_pipeline_version": "abc1234",
    }
    validate_done_dict(data, job_dir=tmp_path)


def test_rejects_unknown_field() -> None:
    with pytest.raises(ValueError, match="unknown"):
        validate_done_dict(
            {
                "done_schema": 1,
                "job_id": "job1",
                "doc_id": "123",
                "created_at": "t",
                "source_pdf": "123.pdf",
                "artifacts": [{"path": "123.txt", "sha256": "a" * 64}],
                "ocr_pipeline_version": "x",
                "extra": 1,
            }
        )


def test_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="traversal|invalid"):
        validate_done_dict(
            {
                "done_schema": 1,
                "job_id": "job1",
                "doc_id": "123",
                "created_at": "t",
                "source_pdf": "123.pdf",
                "artifacts": [{"path": "../x.txt", "sha256": "a" * 64}],
                "ocr_pipeline_version": "x",
            }
        )


def test_content_hash_stable() -> None:
    assert content_hash("a\r\nb") == content_hash("a\nb")


def test_validate_done_with_figures_artifact(tmp_path: Path) -> None:
    txt = tmp_path / "123.txt"
    txt.write_text("hello\n", encoding="utf-8")
    figures = tmp_path / "figures"
    figures.mkdir()
    png = figures / "p001_b012.png"
    png.write_bytes(b"x")
    data = {
        "done_schema": 1,
        "job_id": "20260724-123-001",
        "doc_id": "123",
        "created_at": "2026-07-24T00:00:00+00:00",
        "source_pdf": "123.pdf",
        "artifacts": [
            {"path": "123.txt", "sha256": sha256_file(txt)},
            {"path": "figures/p001_b012.png", "sha256": sha256_file(png)},
        ],
        "ocr_pipeline_version": "abc1234",
    }

    validate_done_dict(data, job_dir=tmp_path)


def test_rejects_unlisted_figure_on_disk(tmp_path: Path) -> None:
    txt = tmp_path / "123.txt"
    txt.write_text("hello\n", encoding="utf-8")
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "p001_b012.png").write_bytes(b"x")
    data = {
        "done_schema": 1,
        "job_id": "20260724-123-001",
        "doc_id": "123",
        "created_at": "2026-07-24T00:00:00+00:00",
        "source_pdf": "123.pdf",
        "artifacts": [{"path": "123.txt", "sha256": sha256_file(txt)}],
        "ocr_pipeline_version": "abc1234",
    }

    with pytest.raises(ValueError, match="figures/p001_b012.png exists"):
        validate_done_dict(data, job_dir=tmp_path)
