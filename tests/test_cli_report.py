"""T5: CLI success / WARN formatting (DR1, DR7, DR8)."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.cli_report import (
    WarnCollector,
    exit_code_for_tex,
    print_success_exit,
)


def test_warn_success_line_joins():
    w = WarnCollector()
    w.add("a", echo=False)
    w.add("b", echo=False)
    assert w.success_line() == "WARN: a; b"


def test_warn_success_line_truncates():
    w = WarnCollector()
    for i in range(20):
        w.add(f"long-warning-number-{i}-xxxxxxxx", echo=False)
    line = w.success_line(max_chars=80)
    assert line is not None
    assert line.startswith("WARN:")
    assert "+more" in line.replace(" ", "") or "more" in line


def test_exit_code_for_tex(tmp_path: Path):
    missing = tmp_path / "no.tex"
    assert exit_code_for_tex(missing) == 1
    present = tmp_path / "yes.tex"
    present.write_text("x", encoding="utf-8")
    assert exit_code_for_tex(present) == 0


def test_print_success_exit_shape(capsys, tmp_path: Path):
    tex = tmp_path / "out.tex"
    tex.write_text("\\documentclass{article}\\begin{document}x\\end{document}", encoding="utf-8")
    w = WarnCollector()
    w.add("layout fullpage fallback (not golden)", echo=False)
    print_success_exit(tex_path=tex, warns=w)
    out = capsys.readouterr().out
    assert "TEX:" in out
    assert "Next: edit <=10m" in out
    assert "latexmk -xelatex out.tex" in out
    assert "WARN: layout fullpage fallback (not golden)" in out
