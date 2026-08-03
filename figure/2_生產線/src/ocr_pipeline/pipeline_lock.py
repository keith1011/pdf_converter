"""Prevent concurrent run_ocr_pipeline on 12GB VRAM."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

DEFAULT_LOCK_NAME = ".ocr_pipeline.lock"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        pass
    # Windows fallback: tasklist
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        body = (out.stdout or "") + (out.stderr or "")
        return str(pid) in body and "No tasks" not in body
    except (OSError, subprocess.SubprocessError):
        return False


class PipelineLock:
    """PID lockfile so two OCR pipelines cannot fight over the same GPU."""

    def __init__(self, path: Path):
        self.path = path
        self._held = False

    def acquire(self) -> None:
        if self.path.exists():
            try:
                other = int(self.path.read_text(encoding="utf-8").strip().splitlines()[0])
            except (OSError, ValueError, IndexError):
                other = -1
            if other != os.getpid() and _pid_alive(other):
                raise RuntimeError(
                    f"Another OCR pipeline is running (pid={other}, lock={self.path}). "
                    "Do not dual-run on 12GB VRAM; wait or delete the lock if stale."
                )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        self._held = True

    def release(self) -> None:
        if not self._held:
            return
        try:
            if self.path.exists():
                cur = self.path.read_text(encoding="utf-8").strip().splitlines()[0]
                if cur == str(os.getpid()):
                    self.path.unlink(missing_ok=True)
        except OSError:
            pass
        self._held = False

    def __enter__(self) -> PipelineLock:
        self.acquire()
        return self

    def __exit__(self, *args) -> None:
        self.release()
