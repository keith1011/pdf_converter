"""Stage1-only layout bakeoff on one page image (no VLM/OCR route).

Run one engine per process (deps live in different venvs)::

  uv run python scripts/layout_bakeoff_789.py --engine surya
  .\\.venv-engines312\\Scripts\\python.exe scripts/layout_bakeoff_789.py --engine doclayout_yolo
  .\\.venv-mineru312\\Scripts\\python.exe scripts/layout_bakeoff_789.py --engine mineru
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _summarize(blocks) -> dict:
    counts: dict[str, int] = {}
    for b in blocks:
        key = b.block_type.value
        counts[key] = counts.get(key, 0) + 1
    return {
        "n_blocks": len(blocks),
        "by_type": counts,
        "blocks": [
            {
                "id": b.block_id,
                "type": b.block_type.value,
                "order": b.order,
                "bbox": [b.bbox.x1, b.bbox.y1, b.bbox.x2, b.bbox.y2],
                "label": (b.meta or {}).get("label"),
            }
            for b in blocks
        ],
    }


def run_one(name: str, analyze_fn, image: Path, page: int = 1) -> dict:
    t0 = time.perf_counter()
    blocks = analyze_fn(image, page)
    elapsed = time.perf_counter() - t0
    summary = _summarize(blocks)
    summary["engine"] = name
    summary["layout_s"] = round(elapsed, 3)
    return summary


def analyze_doclayout(image: Path, page: int):
    from ocr_pipeline.engines.doclayout_yolo import DocLayoutYoloEngine

    eng = DocLayoutYoloEngine(device="cuda")
    try:
        return eng.analyze(image, page)
    finally:
        try:
            eng.release()
        except Exception:
            pass


def analyze_mineru(image: Path, page: int):
    from ocr_pipeline.engines.mineru_layout import MineruLayoutEngine

    eng = MineruLayoutEngine(device="cuda")
    try:
        return eng.analyze(image, page)
    finally:
        try:
            eng.release()
        except Exception:
            pass


def analyze_surya(image: Path, page: int):
    from ocr_pipeline.engines.surya_layout import SuryaLayoutEngine
    from ocr_pipeline.layout import LayoutAnalyzer

    layout = LayoutAnalyzer(dpi=200, device="cuda", force_backend="")
    eng = SuryaLayoutEngine(layout)
    try:
        blocks = eng.analyze(image, page)
        analyze_surya.backend = getattr(layout, "_backend", None)  # type: ignore[attr-defined]
        return blocks
    finally:
        try:
            eng.release()
        except Exception:
            pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--engine",
        required=True,
        choices=("surya", "doclayout_yolo", "mineru"),
    )
    ap.add_argument(
        "--image",
        type=Path,
        default=Path("data/pdf_pages/789/page_001.content.png"),
    )
    args = ap.parse_args()
    image = args.image
    if not image.is_file():
        raise SystemExit(f"missing {image}; render/crop 789 first")

    out_dir = Path("output/layout_bakeoff_789")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== {args.engine} ===")
    if args.engine == "doclayout_yolo":
        r = run_one("doclayout_yolo", analyze_doclayout, image)
    elif args.engine == "mineru":
        r = run_one("mineru", analyze_mineru, image)
    else:
        r = run_one("surya", analyze_surya, image)
        r["surya_backend"] = getattr(analyze_surya, "backend", None)

    print(
        f"  layout_s={r['layout_s']} blocks={r['n_blocks']} by_type={r['by_type']}"
        + (f" backend={r.get('surya_backend')}" if "surya_backend" in r else "")
    )
    path = out_dir / f"{args.engine}.json"
    path.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {path}")


if __name__ == "__main__":
    main()
