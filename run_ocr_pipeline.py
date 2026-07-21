"""
New OCR entrypoint (Surya + dynamic routing + VlmClient).

Legacy path remains: extract_questions.py / run_extract_pipeline.py

Usage:
  .\\.venv\\Scripts\\python.exe run_ocr_pipeline.py data\\sources\\123.pdf
  .\\.venv\\Scripts\\python.exe run_ocr_pipeline.py data\\sources\\123.pdf --limit 1
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
from ocr_pipeline.factory import build_default_pipeline, load_ocr_config


def main() -> None:
    cfg = load_ocr_config(ROOT / "config" / "ocr_pipeline.yaml")
    pipe_cfg = cfg.get("pipeline", {})

    parser = argparse.ArgumentParser(description="Surya + VlmClient OCR pipeline -> .txt + .tex")
    parser.add_argument("pdf", type=Path, help="PDF path")
    parser.add_argument("--limit", type=int, default=0, help="Only first N pages (0=all)")
    parser.add_argument(
        "--polish-per-page",
        action="store_true",
        default=bool(pipe_cfg.get("polish_per_page", False)),
        help="Run Stage3 polish after every page (slower)",
    )
    parser.add_argument(
        "--reuse-images",
        action="store_true",
        help="Reuse existing page PNGs if present",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    print_preflight()
    warns = WarnCollector()
    manager = build_default_pipeline(cfg)
    result = manager.run(
        args.pdf,
        limit=args.limit,
        polish_per_page=args.polish_per_page,
        overwrite=not args.reuse_images,
        warns=warns,
    )
    assert result.tex_path is not None
    print_success_exit(tex_path=result.tex_path, warns=warns)
    raise SystemExit(exit_code_for_tex(result.tex_path))


if __name__ == "__main__":
    main()
