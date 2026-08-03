"""Ship 1.5: optional TeX compile gate (latexmk/xelatex) beside output drafts."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CompileResult:
    ok: bool
    pdf_path: Path | None
    log_path: Path | None
    command: list[str]
    returncode: int
    message: str


def resolve_tex_command() -> list[str] | None:
    """Prefer latexmk -xelatex; else xelatex nonstopmode; else None."""
    if shutil.which("latexmk"):
        return ["latexmk", "-xelatex", "-interaction=nonstopmode"]
    if shutil.which("xelatex"):
        return ["xelatex", "-interaction=nonstopmode"]
    return None


def compile_tex(tex_path: Path, *, timeout_s: int = 300) -> CompileResult:
    """
    Compile ``tex_path`` in its parent directory.

    Always preserves the ``.tex`` draft. Writes/ensures a sibling ``.log``.
    On success, expects sibling ``.pdf``.
    """
    tex_path = tex_path.resolve()
    out_dir = tex_path.parent
    stem = tex_path.stem
    log_path = out_dir / f"{stem}.log"
    pdf_path = out_dir / f"{stem}.pdf"

    cmd_prefix = resolve_tex_command()
    if cmd_prefix is None:
        msg = "TeX toolchain missing: install latexmk or xelatex and ensure PATH"
        log_path.write_text(msg + "\n", encoding="utf-8")
        return CompileResult(
            ok=False,
            pdf_path=None,
            log_path=log_path,
            command=[],
            returncode=127,
            message=msg,
        )

    command = [*cmd_prefix, tex_path.name]
    try:
        proc = subprocess.run(
            command,
            cwd=out_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        blob = (exc.stdout or "") + "\n" + (exc.stderr or "")
        _ensure_log(log_path, blob, fallback=f"compile timed out after {timeout_s}s\n")
        return CompileResult(
            ok=False,
            pdf_path=None,
            log_path=log_path,
            command=command,
            returncode=124,
            message=f"compile timed out; see {log_path.name}",
        )

    combined = (proc.stdout or "") + ("\n" if proc.stderr else "") + (proc.stderr or "")
    _ensure_log(log_path, combined, fallback=f"returncode={proc.returncode}\n")

    if proc.returncode == 0 and pdf_path.is_file() and pdf_path.stat().st_size > 0:
        return CompileResult(
            ok=True,
            pdf_path=pdf_path,
            log_path=log_path,
            command=command,
            returncode=0,
            message="",
        )

    return CompileResult(
        ok=False,
        pdf_path=pdf_path if pdf_path.is_file() else None,
        log_path=log_path,
        command=command,
        returncode=proc.returncode,
        message=f"compile failed; see {log_path.name}",
    )


def _ensure_log(log_path: Path, captured: str, *, fallback: str) -> None:
    """Keep engine log if present; otherwise write captured stdout/stderr."""
    if log_path.is_file() and log_path.stat().st_size > 0:
        if captured.strip():
            # Append CLI capture for debugging without wiping engine log.
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("\n--- cli capture ---\n")
                fh.write(captured)
        return
    text = captured.strip() or fallback
    log_path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def maybe_check_compile(
    *,
    tex_path: Path,
    enabled: bool,
    warn_add,
) -> int:
    """
    Optional compile gate for CLIs.

    ``warn_add`` is typically ``WarnCollector.add``. Returns 0 on skip/success;
    non-zero on compile failure (``.tex`` always kept).
    """
    if not enabled:
        return 0
    result = compile_tex(tex_path)
    if result.ok and result.pdf_path is not None:
        print(f"PDF: {result.pdf_path.resolve()}")
        return 0
    warn_add(result.message or "compile failed")
    return 1 if result.returncode == 0 else int(result.returncode or 1)
