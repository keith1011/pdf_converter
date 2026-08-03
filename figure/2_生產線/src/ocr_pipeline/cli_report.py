"""CLI DX helpers (design-review DR1–DR9). Plain text only — no ANSI."""

from __future__ import annotations

import sys
from pathlib import Path


class WarnCollector:
    """Collect WARN messages; print each on stderr during the run; one line at success."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, msg: str, *, echo: bool = True) -> None:
        msg = msg.strip()
        if not msg or msg in self.items:
            return
        self.items.append(msg)
        if echo:
            print(f"WARN: {msg}", file=sys.stderr)

    def success_line(self, *, max_chars: int = 220) -> str | None:
        """DR8: single WARN: line joined with '; '; truncate with +N more."""
        if not self.items:
            return None
        joined = "; ".join(self.items)
        if len(joined) <= max_chars:
            return f"WARN: {joined}"
        # keep as many full messages as fit
        kept: list[str] = []
        used = 0
        for i, item in enumerate(self.items):
            piece = item if not kept else f"; {item}"
            if used + len(piece) > max_chars - 20:
                rest = len(self.items) - i
                prefix = "; ".join(kept) if kept else self.items[0][: max_chars - 30]
                return f"WARN: {prefix}; +{rest} more (see log)"
            kept.append(item)
            used += len(piece)
        return f"WARN: {'; '.join(kept)}"


def print_preflight() -> None:
    """DR3: once at full-pipeline start."""
    print("Note: Stage3 may take several minutes; silence is OK.")


def print_stage3_start() -> None:
    """DR2: one line then quiet until write."""
    print("Stage3 arrange…")


def print_success_exit(*, tex_path: Path, warns: WarnCollector | None = None) -> None:
    """DR1: TEX / Next / optional one-line WARN."""
    path = tex_path.resolve()
    print(f"TEX: {path}")
    print(f"Next: edit <=10m, then latexmk -xelatex {tex_path.name}")
    if warns is not None:
        line = warns.success_line()
        if line:
            print(line)


def exit_code_for_tex(tex_path: Path | None) -> int:
    """DR7: usable .tex → 0; else non-zero."""
    if tex_path is None:
        return 1
    try:
        return 0 if tex_path.is_file() and tex_path.stat().st_size > 0 else 1
    except OSError:
        return 1
