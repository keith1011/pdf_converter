"""
One-shot pipeline: PDF -> page images -> VLM full-page OCR -> output/<name>.txt + .tex

Usage:
  .\\.venv\\Scripts\\python.exe run_extract_pipeline.py data/sources/paper.pdf
  .\\.venv\\Scripts\\python.exe run_extract_pipeline.py data/sources/paper.pdf --limit 1 --overwrite
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF -> images -> VLM OCR -> .txt + .tex")
    parser.add_argument("pdf", type=Path, help="Path to PDF")
    parser.add_argument("--backend", default="local")
    parser.add_argument(
        "--lang",
        choices=["en", "zh"],
        default="zh",
        help="Source language (default zh)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Only first N pages (smoke test)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output .txt")
    parser.add_argument("--dpi", type=int, default=0, help="Override PDF DPI (0=config default)")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    py = sys.executable
    pdf_cmd = [py, "pdf_to_images.py", str(args.pdf)]
    if args.dpi > 0:
        pdf_cmd.extend(["--dpi", str(args.dpi)])

    print("=== Step 1/2: PDF -> images ===")
    subprocess.run(pdf_cmd, check=True)

    extract_cmd = [
        py,
        "extract_questions.py",
        "--pdf",
        str(args.pdf),
        "--backend",
        args.backend,
        "--lang",
        args.lang,
    ]
    if args.limit > 0:
        extract_cmd.extend(["--limit", str(args.limit)])
    if args.overwrite:
        extract_cmd.append("--overwrite")

    print("\n=== Step 2/2: VLM full-page OCR -> output/*.txt + *.tex ===")
    subprocess.run(extract_cmd, check=True)

    stem = args.pdf.stem
    print(f"\nDone:")
    print(f"  TXT: output\\{stem}.txt")
    print(f"  TEX: output\\{stem}.tex")


if __name__ == "__main__":
    main()
