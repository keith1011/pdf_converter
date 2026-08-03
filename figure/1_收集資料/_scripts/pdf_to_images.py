"""
Convert a PDF into per-page PNG images for VLM extraction.

Usage:
  uv run python 1_收集資料/_scripts/pdf_to_images.py 1_收集資料/data/sources/paper.pdf
  uv run python 1_收集資料/_scripts/pdf_to_images.py 1_收集資料/data/sources/paper.pdf --dpi 200
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "2_生產線" / "config" / "extraction_config.yaml"


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def safe_stem(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem, flags=re.UNICODE)
    return stem.strip("_") or "pdf"


def pdf_to_images(pdf_path: Path, out_dir: Path, dpi: int = 200) -> list[Path]:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise SystemExit(
            "Missing PyMuPDF. Install with:\n"
            "  ..\\AIbuliding\\venv-train\\Scripts\\pip.exe install pymupdf"
        ) from e

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    saved: list[Path] = []

    try:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out_path = out_dir / f"page_{i:03d}.png"
            pix.save(str(out_path))
            saved.append(out_path)
            print(f"  page {i:03d}/{len(doc):03d} -> {out_path}")
    finally:
        doc.close()

    return saved


def main() -> None:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="PDF to PNG pages for VLM extraction")
    parser.add_argument("pdf", type=Path, help="Path to PDF under 1_收集資料/data/sources/ or elsewhere")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: 1_收集資料/data/pdf_pages/<pdf_stem>/)",
    )
    parser.add_argument("--dpi", type=int, default=cfg.get("pdf", {}).get("dpi", 200))
    args = parser.parse_args()

    pdf_path = args.pdf
    configured_pages = Path(cfg["paths"]["pages_dir"])
    if not configured_pages.is_absolute():
        configured_pages = PROJECT_ROOT / configured_pages
    out_dir = args.out_dir or configured_pages / safe_stem(pdf_path)

    print(f"PDF: {pdf_path}")
    print(f"Out: {out_dir} | DPI: {args.dpi}")
    images = pdf_to_images(pdf_path, out_dir, dpi=args.dpi)
    print(f"Done: {len(images)} page image(s)")
    print(f"Next: uv run python 2_生產線/run_ocr_pipeline.py {pdf_path} --reuse-images")


if __name__ == "__main__":
    main()
