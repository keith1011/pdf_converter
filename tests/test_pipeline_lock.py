"""Single-instance OCR lock (Phase 2.8)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ocr_pipeline.pipeline_lock import PipelineLock


def test_lock_blocks_when_other_live_pid_holds_file(tmp_path: Path, monkeypatch):
    path = tmp_path / ".ocr_pipeline.lock"
    path.write_text("424242\n", encoding="utf-8")
    monkeypatch.setattr(
        "ocr_pipeline.pipeline_lock._pid_alive",
        lambda pid: pid == 424242,
    )
    lock = PipelineLock(path)
    with pytest.raises(RuntimeError, match="Another OCR pipeline"):
        lock.acquire()


def test_stale_lock_from_dead_pid_can_be_taken(tmp_path: Path):
    path = tmp_path / ".ocr_pipeline.lock"
    path.write_text("99999999\n", encoding="utf-8")  # almost certainly dead
    lock = PipelineLock(path)
    lock.acquire()
    assert path.read_text(encoding="utf-8").strip() == str(os.getpid())
    lock.release()
    assert not path.exists()
