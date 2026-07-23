"""Ship 1.5: optional --check-compile via shared compile_check helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ocr_pipeline.compile_check import CompileResult, compile_tex, resolve_tex_command


def test_resolve_prefers_latexmk():
    with patch("ocr_pipeline.compile_check.shutil.which") as which:
        which.side_effect = lambda name: "C:/bin/latexmk.exe" if name == "latexmk" else None
        cmd = resolve_tex_command()
    assert cmd is not None
    assert cmd[0] == "latexmk"
    assert "-xelatex" in cmd


def test_resolve_falls_back_to_xelatex():
    with patch("ocr_pipeline.compile_check.shutil.which") as which:
        which.side_effect = lambda name: "C:/bin/xelatex.exe" if name == "xelatex" else None
        cmd = resolve_tex_command()
    assert cmd is not None
    assert cmd[0] == "xelatex"
    assert "-interaction=nonstopmode" in cmd


def test_resolve_none_when_toolchain_missing():
    with patch("ocr_pipeline.compile_check.shutil.which", return_value=None):
        assert resolve_tex_command() is None


def test_compile_success_writes_pdf_keeps_tex(tmp_path: Path):
    tex = tmp_path / "demo.tex"
    tex.write_text(
        "\\documentclass{article}\\begin{document}hi\\end{document}\n",
        encoding="utf-8",
    )
    pdf = tmp_path / "demo.pdf"

    def fake_run(cmd, **kwargs):
        pdf.write_bytes(b"%PDF")
        (tmp_path / "demo.log").write_text("This is XeTeX, Version\n", encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    with (
        patch("ocr_pipeline.compile_check.resolve_tex_command", return_value=["latexmk", "-xelatex"]),
        patch("ocr_pipeline.compile_check.subprocess.run", side_effect=fake_run) as run,
    ):
        result = compile_tex(tex)

    assert result.ok is True
    assert result.pdf_path == pdf
    assert result.log_path == tmp_path / "demo.log"
    assert result.log_path.is_file()
    assert tex.is_file()
    assert pdf.is_file()
    assert run.call_args.kwargs.get("cwd") == tmp_path


def test_compile_failure_keeps_tex_and_writes_sibling_log(tmp_path: Path):
    tex = tmp_path / "bad.tex"
    tex.write_text("\\documentclass{article}\\begin{document}\\oops\\end{document}\n", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        (tmp_path / "bad.log").write_text("! Undefined control sequence.\n", encoding="utf-8")
        return MagicMock(returncode=1, stdout="", stderr="error")

    with (
        patch("ocr_pipeline.compile_check.resolve_tex_command", return_value=["xelatex", "-interaction=nonstopmode"]),
        patch("ocr_pipeline.compile_check.subprocess.run", side_effect=fake_run),
    ):
        result = compile_tex(tex)

    assert result.ok is False
    assert result.pdf_path is None or not (result.pdf_path and result.pdf_path.is_file())
    assert tex.is_file(), "draft .tex must survive compile failure"
    assert result.log_path == tmp_path / "bad.log"
    assert result.log_path.is_file()
    assert "compile" in result.message.lower() or "failed" in result.message.lower()


def test_compile_missing_toolchain_clear_message(tmp_path: Path):
    tex = tmp_path / "solo.tex"
    tex.write_text("\\documentclass{article}\\begin{document}x\\end{document}\n", encoding="utf-8")

    with patch("ocr_pipeline.compile_check.resolve_tex_command", return_value=None):
        result = compile_tex(tex)

    assert result.ok is False
    assert tex.is_file()
    assert "latexmk" in result.message.lower() or "xelatex" in result.message.lower()
    assert result.log_path is not None
    assert result.log_path.is_file()


def test_compile_result_dataclass_fields():
    r = CompileResult(
        ok=False,
        pdf_path=None,
        log_path=Path("a.log"),
        command=[],
        returncode=127,
        message="missing",
    )
    assert r.ok is False
    assert r.returncode == 127
