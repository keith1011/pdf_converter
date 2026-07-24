from __future__ import annotations

import time
from contextlib import contextmanager


class StageTimer:
    def __init__(self) -> None:
        self._stages: dict[str, float] = {}
        self._t0 = time.perf_counter()

    @contextmanager
    def section(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self._stages[name] = self._stages.get(name, 0.0) + (time.perf_counter() - start)

    def as_dict(self) -> dict[str, float]:
        out = dict(self._stages)
        out["total"] = time.perf_counter() - self._t0
        return out
