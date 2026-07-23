"""
New OCR entrypoint (Surya + dynamic routing + VlmClient).

Legacy path remains: extract_questions.py / run_extract_pipeline.py

Usage:
  .\\.venv\\Scripts\\python.exe run_ocr_pipeline.py data\\sources\\123.pdf
  .\\.venv\\Scripts\\python.exe run_ocr_pipeline.py data\\sources\\123.pdf --limit 1
  .\\.venv\\Scripts\\python.exe run_ocr_pipeline.py data\\sources\\123.pdf --check-compile
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ocr_pipeline.cli_report import (
    WarnCollector,
    exit_code_for_tex,
    print_preflight,
    print_success_exit,
)
from ocr_pipeline.compile_check import maybe_check_compile
from ocr_pipeline.factory import build_default_pipeline, load_ocr_config


def build_parser(pipe_cfg: dict | None = None) -> argparse.ArgumentParser:
    pipe_cfg = pipe_cfg or {}
    parser = argparse.ArgumentParser(description="Surya + VlmClient OCR pipeline -> .txt + .tex")
    parser.add_argument("pdf", type=Path, help="PDF path")
    parser.add_argument("--limit", type=int, default=0, help="Only first N pages (0=all)")
    parser.add_argument(
        "--polish-per-page",
        action="store_true",
        default=bool(pipe_cfg.get("polish_per_page", False)),
        help="Deprecated no-op: content-first always polishes each page",
    )
    parser.add_argument(
        "--reuse-images",
        action="store_true",
        help="Reuse existing page PNGs if present",
    )
    parser.add_argument(
        "--reuse-layout",
        action="store_true",
        help="Skip Surya; load data/pdf_pages/<stem>/layout.json (implies image reuse)",
    )
    parser.add_argument(
        "--check-compile",
        action="store_true",
        help="After writing .tex, run latexmk/xelatex in the output dir (Ship 1.5)",
    )
    parser.add_argument(
        "--allow-concurrent",
        action="store_true",
        help="Allow a second pipeline (unsafe on 12GB; default is single-instance lock)",
    )
    return parser


def main() -> None:
    cfg = load_ocr_config(ROOT / "config" / "ocr_pipeline.yaml")
    pipe_cfg = cfg.get("pipeline", {})

    parser = build_parser(pipe_cfg)
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    print_preflight()
    warns = WarnCollector()
    manager = build_default_pipeline(cfg)
    reuse_layout = bool(args.reuse_layout)
    overwrite = not (args.reuse_images or reuse_layout)
    lock_enabled = bool(pipe_cfg.get("single_instance_lock", True)) and not args.allow_concurrent
    try:
        result = manager.run(
            args.pdf,
            limit=args.limit,
            polish_per_page=args.polish_per_page,
            overwrite=overwrite,
            reuse_layout=reuse_layout,
            single_instance_lock=lock_enabled,
            warns=warns,
        )
    except RuntimeError as e:
        raise SystemExit(str(e)) from e
    assert result.tex_path is not None
    compile_code = maybe_check_compile(
        tex_path=result.tex_path,
        enabled=args.check_compile,
        warn_add=warns.add,
    )
    print_success_exit(tex_path=result.tex_path, warns=warns)
    base = exit_code_for_tex(result.tex_path)
    raise SystemExit(base if compile_code == 0 else compile_code)


if __name__ == "__main__":
    main()
