from __future__ import annotations

from pathlib import Path

import pytest

from ocr_pipeline.job_stage import stage_job_dir


def test_stage_job_dir_copies_figures(tmp_path: Path) -> None:
    out = tmp_path / "output"
    out.mkdir()
    (out / "123.txt").write_text("hi", encoding="utf-8")
    (out / "123.pageir.json").write_text("{}", encoding="utf-8")
    figures = out / "123" / "figures"
    figures.mkdir(parents=True)
    (figures / "p001_b012.png").write_bytes(b"PNG")

    destination = stage_job_dir(
        doc_id="123",
        output_dir=out,
        staging_dir=tmp_path / "stage",
    )

    assert (destination / "123.txt").is_file()
    assert (destination / "123.pageir.json").is_file()
    assert (destination / "figures" / "p001_b012.png").is_file()


def test_stage_job_dir_requires_text_artifact(tmp_path: Path) -> None:
    out = tmp_path / "output"
    out.mkdir()

    with pytest.raises(FileNotFoundError):
        stage_job_dir(doc_id="123", output_dir=out, staging_dir=tmp_path / "stage")
