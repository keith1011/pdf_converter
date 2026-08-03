"""Run DSE Math CP Paper 2 MCQ OCR for 2012--2023 in the foreground.

The runner intentionally rebuilds each specialized MCQ layout with the
layout CLI's default ``--skip-first-page`` setting, then routes only the
resulting question crops through the VLM. It does not publish or ingest.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LINE_ROOT = Path(__file__).resolve().parents[1]
ROOT = LINE_ROOT.parent
SOURCES = ROOT / "1_收集資料" / "data" / "sources"
PAGES_ROOT = ROOT / "1_收集資料" / "data" / "pdf_pages"
OUTPUT = ROOT / "3.分析結果" / "output"
LOG = OUTPUT / "cross_year_2012_2023.run.log"
SUMMARY = OUTPUT / "cross_year_2012_2023.summary.json"
DOC_IDS = tuple(f"{year}p2" for year in range(2012, 2024))
EXPECTED_QIDS = tuple(range(1, 46))
TEXT_ENGINE = "paddleocr_vl"
OUTPUT_TAG = "paddle"


@dataclass(frozen=True)
class LayoutValidation:
    cover_excluded: bool
    question_ids: tuple[int, ...]
    boxes: int

    @property
    def complete(self) -> bool:
        return self.cover_excluded and self.question_ids == EXPECTED_QIDS


def stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def console(line: str, *, end: str = "\n") -> None:
    """Print child output even when the Windows console uses a legacy code page."""
    try:
        print(line, end=end, flush=True)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe = line.encode(encoding, errors="replace").decode(encoding)
        print(safe, end=end, flush=True)


def log(message: str) -> None:
    line = f"{stamp()} {message}"
    console(line)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run_step(doc_id: str, name: str, command: list[str]) -> tuple[int, float]:
    log(f"{doc_id} {name}_START command={subprocess.list2cmdline(command)}")
    started = time.perf_counter()
    with LOG.open("a", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            console(line, end="")
            fh.write(line)
        rc = proc.wait()
    elapsed = time.perf_counter() - started
    log(f"{doc_id} {name}_DONE rc={rc} seconds={elapsed:.1f}")
    return rc, elapsed


def page_images_exist(pages_dir: Path) -> bool:
    return any(pages_dir.glob("page_*.png"))


def validate_mcq_layout(layout_path: Path) -> LayoutValidation:
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    pages = data.get("pages", [])
    includes_cover = any(int(page.get("page", -1)) == 1 for page in pages)
    blocks = [block for page in pages for block in page.get("blocks", [])]
    question_ids = tuple(
        sorted(
            qid
            for block in blocks
            if isinstance((qid := block.get("meta", {}).get("question_id")), int)
        )
    )
    return LayoutValidation(
        cover_excluded=not includes_cover,
        question_ids=question_ids,
        boxes=len(blocks),
    )


def build_ocr_command(
    pdf: Path,
    *,
    crop_dir: Path,
    output_tag: str = OUTPUT_TAG,
    text_engine: str = TEXT_ENGINE,
) -> list[str]:
    return [
        "uv",
        "run",
        "python",
        str(LINE_ROOT / "run_ocr_pipeline.py"),
        str(pdf),
        "--dse-mcq",
        "--reuse-images",
        "--reuse-layout",
        "--text-engine",
        text_engine,
        "--crop-dir",
        str(crop_dir),
        "--output-tag",
        output_tag,
    ]


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    LOG.write_text("", encoding="utf-8")
    results: list[dict[str, object]] = []
    total_started = time.perf_counter()
    log("BATCH_START docs=" + ",".join(DOC_IDS))
    log("POLICY skip page_001 (DSE Paper 2 candidate instructions); no publish; no ingest")

    for index, doc_id in enumerate(DOC_IDS, start=1):
        pdf = SOURCES / f"{doc_id}.pdf"
        pages_dir = PAGES_ROOT / doc_id
        layout_path = pages_dir / "layout.json"
        work_dir = OUTPUT / f"dse_mcq_layout_{doc_id}"
        row: dict[str, object] = {"doc_id": doc_id, "pdf": str(pdf), "steps": {}}
        results.append(row)
        log(f"DOC_START {index}/{len(DOC_IDS)} {doc_id}")

        if not pdf.is_file():
            row["error"] = "missing PDF"
            log(f"DOC_FAIL {doc_id} missing PDF: {pdf}")
            continue

        if not page_images_exist(pages_dir):
            rc, seconds = run_step(
                doc_id,
                "RENDER",
                [
                    "uv",
                    "run",
                    "python",
                    "pdf_to_images.py",
                    str(pdf),
                    "--out-dir",
                    str(pages_dir),
                ],
            )
            row["steps"]["render"] = {"rc": rc, "seconds": round(seconds, 1)}
            if rc:
                row["error"] = "render failed"
                log(f"DOC_FAIL {doc_id} render")
                continue
        else:
            log(f"{doc_id} RENDER_SKIP existing page images")

        if layout_path.is_file():
            log(f"{doc_id} LAYOUT_SKIP existing layout (preserved)")
            row["steps"]["layout"] = {"rc": 0, "seconds": 0.0, "reused": True}
        else:
            rc, seconds = run_step(
                doc_id,
                "LAYOUT",
                [
                    "uv",
                    "run",
                    "--with",
                    "rapidocr-onnxruntime",
                    "python",
                    str(LINE_ROOT / "_script" / "dse_mcq_layout_doc.py"),
                    "--pages-dir",
                    str(pages_dir),
                    "--pdf",
                    str(pdf),
                    "--out-dir",
                    str(pages_dir),
                    "--work-dir",
                    str(work_dir),
                    "--no-backup-layout",
                ],
            )
            row["steps"]["layout"] = {"rc": rc, "seconds": round(seconds, 1)}
            if rc or not layout_path.is_file():
                row["error"] = "layout failed"
                log(f"DOC_FAIL {doc_id} layout")
                continue

        layout = validate_mcq_layout(layout_path)
        row["layout"] = {
            "cover_excluded": layout.cover_excluded,
            "boxes": layout.boxes,
            "question_ids": list(layout.question_ids),
            "complete": layout.complete,
        }
        log(
            f"{doc_id} LAYOUT_VERIFY cover_excluded={layout.cover_excluded} "
            f"boxes={layout.boxes} qids={len(layout.question_ids)}/45 "
            f"complete={layout.complete}"
        )
        if not layout.complete:
            row["error"] = "layout is not exact Q1-Q45"
            log(f"DOC_FAIL {doc_id} layout is not exact Q1-Q45; OCR not started")
            continue

        crop_dir = OUTPUT / "crops" / f"{doc_id}.{OUTPUT_TAG}"
        questions_path = OUTPUT / f"{doc_id}.{OUTPUT_TAG}.questions.jsonl"
        if crop_dir.exists() or questions_path.exists():
            row["error"] = "target output already exists"
            log(
                f"DOC_FAIL {doc_id} target exists; preserving "
                f"{crop_dir} / {questions_path}"
            )
            continue

        rc, seconds = run_step(
            doc_id,
            "OCR",
            build_ocr_command(pdf, crop_dir=crop_dir),
        )
        row["steps"]["ocr"] = {"rc": rc, "seconds": round(seconds, 1)}
        if rc:
            row["error"] = "OCR failed"
            log(f"DOC_FAIL {doc_id} OCR")
        else:
            log(f"DOC_DONE {doc_id}")

        SUMMARY.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    total_seconds = time.perf_counter() - total_started
    SUMMARY.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [row["doc_id"] for row in results if "error" in row]
    log(f"BATCH_DONE seconds={total_seconds:.1f} failures={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
