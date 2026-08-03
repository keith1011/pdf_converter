"""CLI wiring for optional --check-compile on both entrypoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import arrange_only
import run_ocr_pipeline

from ocr_pipeline.cli_report import WarnCollector
from ocr_pipeline.compile_check import CompileResult, maybe_check_compile


def test_run_ocr_pipeline_parser_exposes_check_compile():
    parser = run_ocr_pipeline.build_parser({})
    args = parser.parse_args(["dummy.pdf", "--check-compile"])
    assert args.check_compile is True
    args_off = parser.parse_args(["dummy.pdf"])
    assert args_off.check_compile is False


def test_run_ocr_pipeline_parser_exposes_reuse_layout_and_allow_concurrent():
    parser = run_ocr_pipeline.build_parser({})
    args = parser.parse_args(["dummy.pdf", "--reuse-layout", "--allow-concurrent"])
    assert args.reuse_layout is True
    assert args.allow_concurrent is True


def test_run_ocr_pipeline_parser_exposes_dse_mcq_mode():
    parser = run_ocr_pipeline.build_parser({})

    args = parser.parse_args(["dummy.pdf", "--dse-mcq"])

    assert args.dse_mcq is True


def test_run_ocr_pipeline_parser_accepts_a_text_engine_override():
    parser = run_ocr_pipeline.build_parser({})

    args = parser.parse_args(["dummy.pdf", "--text-engine", "paddleocr_vl"])

    assert args.text_engine == "paddleocr_vl"


def test_run_ocr_pipeline_parser_accepts_a_crop_dir_override():
    parser = run_ocr_pipeline.build_parser({})

    args = parser.parse_args(["dummy.pdf", "--crop-dir", "3.分析結果/output/crops/test-run"])

    assert args.crop_dir == Path("3.分析結果/output/crops/test-run")


def test_arrange_only_parser_exposes_check_compile():
    parser = arrange_only.build_parser()
    args = parser.parse_args(["dummy.txt", "--check-compile"])
    assert args.check_compile is True


def test_maybe_check_compile_success_prints_pdf(capsys, tmp_path: Path):
    tex = tmp_path / "ok.tex"
    tex.write_text("x", encoding="utf-8")
    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(b"%PDF")
    log = tmp_path / "ok.log"
    log.write_text("ok", encoding="utf-8")
    warns = WarnCollector()

    with patch(
        "ocr_pipeline.compile_check.compile_tex",
        return_value=CompileResult(
            ok=True,
            pdf_path=pdf,
            log_path=log,
            command=["latexmk", "-xelatex", "ok.tex"],
            returncode=0,
            message="",
        ),
    ):
        code = maybe_check_compile(tex_path=tex, enabled=True, warn_add=warns.add)

    out = capsys.readouterr().out
    assert code == 0
    assert f"PDF: {pdf.resolve()}" in out
    assert not warns.items


def test_maybe_check_compile_failure_keeps_tex_warns(tmp_path: Path):
    tex = tmp_path / "bad.tex"
    tex.write_text("x", encoding="utf-8")
    log = tmp_path / "bad.log"
    log.write_text("! error", encoding="utf-8")
    warns = WarnCollector()

    with patch(
        "ocr_pipeline.compile_check.compile_tex",
        return_value=CompileResult(
            ok=False,
            pdf_path=None,
            log_path=log,
            command=["xelatex", "bad.tex"],
            returncode=1,
            message=f"compile failed; see {log.name}",
        ),
    ):
        code = maybe_check_compile(tex_path=tex, enabled=True, warn_add=warns.add)

    assert code != 0
    assert tex.is_file()
    assert any("compile" in w.lower() for w in warns.items)


def test_maybe_check_compile_disabled_is_noop(tmp_path: Path):
    tex = tmp_path / "skip.tex"
    tex.write_text("x", encoding="utf-8")
    warns = WarnCollector()
    with patch("ocr_pipeline.compile_check.compile_tex") as compile_tex:
        code = maybe_check_compile(tex_path=tex, enabled=False, warn_add=warns.add)
    compile_tex.assert_not_called()
    assert code == 0
