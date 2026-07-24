"""
New OCR entrypoint (Surya + dynamic routing + VlmClient).

Legacy path remains: extract_questions.py / run_extract_pipeline.py

Usage:
  uv run python run_ocr_pipeline.py data/sources/123.pdf
  uv run python run_ocr_pipeline.py data/sources/123.pdf --limit 1
  uv run python run_ocr_pipeline.py data/sources/123.pdf --check-compile
  uv run python run_ocr_pipeline.py data/sources/123.pdf --publish --ingest
  uv run python run_ocr_pipeline.py path/to/789.pdf --doc-type question_paper --limit 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ocr_pipeline.cli_report import (
    WarnCollector,
    exit_code_for_tex,
    print_preflight,
    print_success_exit,
)
from ocr_pipeline.compile_check import maybe_check_compile
from ocr_pipeline.job_export import publish_and_ingest


def build_parser(pipe_cfg: dict | None = None) -> argparse.ArgumentParser:
    pipe_cfg = pipe_cfg or {}
    parser = argparse.ArgumentParser(description="Surya + VlmClient OCR pipeline -> .txt + .tex")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional YAML config (default: config/ocr_pipeline.yaml)",
    )
    parser.add_argument("pdf", type=Path, nargs="?", default=None, help="PDF path")
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
    parser.add_argument(
        "--skip-polish",
        action="store_true",
        default=bool(pipe_cfg.get("skip_polish", False)),
        help="Skip Stage3 VLM polish and finalize stitched drafts directly",
    )
    parser.add_argument(
        "--output-tag",
        default=str(pipe_cfg.get("output_tag", "")),
        help="Optional artifact suffix: source.<tag>.tex",
    )
    parser.add_argument(
        "--doc-type",
        default=str(pipe_cfg.get("doc_type", "marking_scheme")),
        choices=("marking_scheme", "question_paper"),
        help="marking_scheme=content-first default; question_paper=stem extract only",
    )
    parser.add_argument(
        "--content-crop",
        action="store_true",
        default=bool(pipe_cfg.get("apply_content_crop", False)),
        help="Crop each page to DSE content box before layout/OCR",
    )
    parser.add_argument(
        "--doc-id",
        default=None,
        help="DONE/Qdrant doc_id (default: PDF stem, without output-tag)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="After OCR, stage artifacts and publish DONE job to --share-root",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Ingest published job into Qdrant (needs --publish or --job-dir)",
    )
    parser.add_argument(
        "--share-root",
        type=Path,
        default=Path("Z:/"),
        help="Samba share root containing jobs/ (default Z:/)",
    )
    parser.add_argument(
        "--job-dir",
        type=Path,
        default=None,
        help="Existing job dir for --ingest without --publish (skips OCR if no pdf)",
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Delete existing doc_id points before ingest",
    )
    return parser


def main() -> None:
    from ocr_pipeline.factory import build_default_pipeline, load_ocr_config

    # Pre-parse --config so defaults match the selected branch YAML
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", type=Path, default=None)
    pre_args, _ = pre.parse_known_args()
    cfg_path = pre_args.config or (ROOT / "config" / "ocr_pipeline.yaml")
    cfg = load_ocr_config(cfg_path)
    pipe_cfg = cfg.get("pipeline", {})

    parser = build_parser(pipe_cfg)
    args = parser.parse_args()

    # Ingest-only path: no PDF, use existing --job-dir
    if args.pdf is None:
        if not (args.ingest and args.job_dir):
            parser.error("pdf is required unless --ingest --job-dir (ingest-only)")
        publish_and_ingest(
            output_dir=ROOT / "output",
            artifact_stem="",  # unused when not publishing
            doc_id=args.doc_id or "unused",
            share_root=args.share_root,
            do_publish=False,
            do_ingest=True,
            job_dir=args.job_dir,
            reindex=args.reindex,
        )
        raise SystemExit(0)

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    if args.ingest and not args.publish and args.job_dir is None:
        parser.error("--ingest requires --publish or --job-dir")

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
            skip_polish=args.skip_polish,
            output_tag=args.output_tag,
            doc_type=args.doc_type,
            apply_content_crop=bool(args.content_crop),
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

    doc_id = args.doc_id or args.pdf.stem
    if args.publish or (args.ingest and args.job_dir is not None):
        out_dir = result.tex_path.parent
        publish_and_ingest(
            output_dir=out_dir,
            artifact_stem=result.source,
            doc_id=doc_id,
            share_root=args.share_root,
            source_pdf=args.pdf.name,
            do_publish=bool(args.publish),
            do_ingest=bool(args.ingest),
            job_dir=args.job_dir,
            reindex=args.reindex,
        )

    base = exit_code_for_tex(result.tex_path)
    raise SystemExit(base if compile_code == 0 else compile_code)


if __name__ == "__main__":
    main()
