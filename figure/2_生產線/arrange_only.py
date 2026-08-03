"""
Re-run Stage3 arrange only: draft/txt -> polished .txt + .tex
(does not re-run Surya / crop OCR)

Usage:
  uv run python 2_生產線/arrange_only.py 3.分析結果/output/123.txt
  uv run python 2_生產線/arrange_only.py 3.分析結果/output/123.txt --out-prefix 3.分析結果/output/123
  uv run python 2_生產線/arrange_only.py 3.分析結果/output/123.txt --no-vlm
  uv run python 2_生產線/arrange_only.py 3.分析結果/output/123.txt --no-vlm --check-compile
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.cli_report import (
    WarnCollector,
    exit_code_for_tex,
    print_stage3_start,
    print_success_exit,
)
from ocr_pipeline.compile_check import maybe_check_compile
from ocr_pipeline.factory import load_ocr_config
from ocr_pipeline.latex_math import sanitize_tex_document, strip_model_junk
from ocr_pipeline.vlm_client import build_vlm_client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage3 only: polish draft -> txt+tex")
    parser.add_argument("draft", type=Path, help="Input draft/txt path")
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=None,
        help="Output prefix (default: same stem as draft)",
    )
    parser.add_argument(
        "--no-vlm",
        action="store_true",
        help="Only run local sanitize on an existing .tex beside the draft",
    )
    parser.add_argument(
        "--check-compile",
        action="store_true",
        help="After writing .tex, run latexmk/xelatex in the output dir (Ship 1.5)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.draft.exists():
        raise SystemExit(f"Not found: {args.draft}")

    prefix = args.out_prefix or args.draft.with_suffix("")
    txt_out = Path(str(prefix) + ".txt")
    tex_out = Path(str(prefix) + ".tex")
    warns = WarnCollector()

    draft = args.draft.read_text(encoding="utf-8")

    if args.no_vlm:
        if tex_out.exists():
            tex = sanitize_tex_document(tex_out.read_text(encoding="utf-8"))
        else:
            tex = FinalPolisher.wrap_tex(draft)
            tex = sanitize_tex_document(tex)
            warns.add("no existing .tex; wrapped draft then sanitized")
        txt_out.write_text(strip_model_junk(draft), encoding="utf-8")
        tex_out.write_text(tex, encoding="utf-8")
        compile_code = maybe_check_compile(
            tex_path=tex_out, enabled=args.check_compile, warn_add=warns.add
        )
        print_success_exit(tex_path=tex_out, warns=warns)
        base = exit_code_for_tex(tex_out)
        raise SystemExit(base if compile_code == 0 else compile_code)

    cfg = load_ocr_config(ROOT / "config" / "ocr_pipeline.yaml")
    vlm = build_vlm_client(cfg)
    polisher = FinalPolisher(vlm)
    print_stage3_start()
    txt, tex, pw = polisher.polish(draft)
    for w in pw:
        warns.add(w)
    txt_out.write_text(txt, encoding="utf-8")
    tex_out.write_text(tex, encoding="utf-8")
    compile_code = maybe_check_compile(
        tex_path=tex_out, enabled=args.check_compile, warn_add=warns.add
    )
    print_success_exit(tex_path=tex_out, warns=warns)
    base = exit_code_for_tex(tex_out)
    raise SystemExit(base if compile_code == 0 else compile_code)


if __name__ == "__main__":
    main()
