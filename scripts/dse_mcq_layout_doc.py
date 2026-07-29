"""Build full-doc DSE MCQ layout.json from page PNGs + light OCR.

Example::

    uv run --with rapidocr-onnxruntime python scripts/dse_mcq_layout_doc.py \\
      --pages-dir data/pdf_pages/2015p2 \\
      --pdf data/sources/2015p2.pdf \\
      --profile config/profiles/math_cp_p2.yaml \\
      --out-dir data/pdf_pages/2015p2 \\
      --work-dir output/dse_mcq_layout_2015p2
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from PIL import Image  # noqa: E402

from ocr_pipeline.dse_mcq_layout import (  # noqa: E402
    regions_to_layout_blocks,
    select_mcq_page_images,
)
from ocr_pipeline.dse_mcq_ocr import load_ocr_lines_json  # noqa: E402
from ocr_pipeline.dse_mcq_profile import default_math_cp_p2_path, load_mcq_profile  # noqa: E402
from ocr_pipeline.dse_mcq_region import detect_mcq_regions  # noqa: E402
from ocr_pipeline.dse_mcq_types import OcrLine  # noqa: E402
from ocr_pipeline.layout_artifact import layout_artifact_path, save_layout_artifact  # noqa: E402
from ocr_pipeline.models import PageResult  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("dse_mcq_layout_doc")


def _rapidocr_lines(image_path: Path) -> list[OcrLine]:
    from rapidocr_onnxruntime import RapidOCR

    ocr = RapidOCR()
    result, _elapse = ocr(str(image_path))
    w, h = Image.open(image_path).size
    lines: list[OcrLine] = []
    for item in result or []:
        box, text, _score = item[0], item[1], item[2]
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        lines.append(
            OcrLine(
                text=str(text),
                bbox=(float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))),
                page_width=float(w),
                page_height=float(h),
            )
        )
    lines.sort(key=lambda ln: (ln.bbox[1], ln.bbox[0]))
    return lines


def _dump_lines_json(lines: list[OcrLine], path: Path) -> None:
    if not lines:
        payload = {"page_width": 0, "page_height": 0, "lines": []}
    else:
        payload = {
            "page_width": lines[0].page_width,
            "page_height": lines[0].page_height,
            "lines": [{"text": ln.text, "bbox": list(ln.bbox)} for ln in lines],
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _draw_overlay(image_path: Path, page_result: PageResult, out_path: Path) -> None:
    img = Image.open(image_path).convert("RGB")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    colors = [(255, 0, 0), (0, 128, 255), (0, 180, 0), (200, 0, 200), (255, 140, 0)]
    for i, b in enumerate(page_result.blocks):
        c = colors[i % len(colors)]
        box = [b.bbox.x1, b.bbox.y1, b.bbox.x2, b.bbox.y2]
        draw.rectangle(box, outline=c, width=4)
        qid = (b.meta or {}).get("question_id", "?")
        draw.text((box[0] + 6, max(0, box[1] - 22)), f"Q{qid}", fill=c)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Full-doc DSE MCQ layout from page PNGs")
    p.add_argument("--pages-dir", type=Path, required=True, help="Dir with page_XXX.png")
    p.add_argument("--pdf", type=Path, default=None)
    p.add_argument("--profile", type=Path, default=None)
    p.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Where to write layout.json + crops/ (usually the pages-dir)",
    )
    p.add_argument(
        "--work-dir",
        type=Path,
        required=True,
        help="Debug dir for lines.json / overlay.png per page",
    )
    p.add_argument(
        "--lines-dir",
        type=Path,
        default=None,
        help="If set, load page_XXX.lines.json from here instead of running OCR",
    )
    p.add_argument("--backup-layout", action="store_true", default=True)
    p.add_argument("--no-backup-layout", action="store_false", dest="backup_layout")
    p.add_argument("--overlays", action="store_true", default=True)
    p.add_argument("--no-overlays", action="store_false", dest="overlays")
    p.add_argument(
        "--skip-first-page",
        action="store_true",
        default=True,
        help="Skip PDF page 1 (DSE Paper 2 candidate instructions; default)",
    )
    p.add_argument(
        "--include-first-page",
        action="store_false",
        dest="skip_first_page",
        help="Include PDF page 1 when it contains questions",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profile = load_mcq_profile(args.profile or default_math_cp_p2_path())
    pages_dir: Path = args.pages_dir
    pngs = select_mcq_page_images(
        sorted(pages_dir.glob("page_*.png")), skip_first_page=args.skip_first_page
    )
    if not pngs:
        logger.error("No page_*.png under %s", pages_dir)
        return 2

    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    crops_dir = args.out_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    artifact = layout_artifact_path(args.out_dir)
    if args.backup_layout and artifact.exists():
        bak = artifact.with_suffix(".json.bak_mineru")
        if not bak.exists():
            shutil.copy2(artifact, bak)
            logger.info("Backed up existing layout → %s", bak)

    page_results: list[PageResult] = []
    summary: list[dict] = []

    for png in pngs:
        # page_004.png → 4
        page_no = int(png.stem.split("_")[1])
        lines_path = args.work_dir / f"page_{page_no:03d}.lines.json"
        if args.lines_dir is not None:
            src = args.lines_dir / f"page_{page_no:03d}.lines.json"
            if not src.exists():
                src = args.lines_dir / f"{png.stem}.lines.json"
            lines = load_ocr_lines_json(src)
            _dump_lines_json(lines, lines_path)
        else:
            logger.info("OCR page %s …", page_no)
            lines = _rapidocr_lines(png)
            _dump_lines_json(lines, lines_path)

        try:
            regions = detect_mcq_regions(lines, profile)
        except Exception:
            logger.exception("detect_mcq_regions crashed on page %s", page_no)
            regions = []

        if regions:
            blocks = regions_to_layout_blocks(
                png,
                regions,
                page=page_no,
                profile_id=profile.id,
                crops_dir=crops_dir,
            )
        else:
            blocks = []
            logger.warning("page %s: 0 regions (empty layout page / non-MCQ)", page_no)

        pr = PageResult(page=page_no, image_path=png, blocks=blocks)
        page_results.append(pr)
        incomplete = sum(1 for r in regions if r.incomplete)
        summary.append(
            {
                "page": page_no,
                "lines": len(lines),
                "questions": len(regions),
                "incomplete": incomplete,
                "qids": [r.question_id for r in regions],
            }
        )
        if args.overlays and blocks:
            _draw_overlay(png, pr, args.work_dir / f"page_{page_no:03d}.overlay.png")

    save_layout_artifact(
        artifact,
        source=f"dse_mcq_region:{profile.id}",
        pdf_path=args.pdf,
        pages=page_results,
    )
    summary_path = args.work_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    total_q = sum(s["questions"] for s in summary)
    total_inc = sum(s["incomplete"] for s in summary)
    logger.info("Wrote %s (%d pages, %d questions, %d incomplete)", artifact, len(page_results), total_q, total_inc)
    logger.info("Summary %s", summary_path)
    for s in summary:
        logger.info(
            "  p%02d  q=%d  incomplete=%d  qids=%s  lines=%d",
            s["page"],
            s["questions"],
            s["incomplete"],
            s["qids"],
            s["lines"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
