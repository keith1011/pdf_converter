"""Batch publish→ingest from local output/ (ingest contract).

Usage:
  uv run python -m ocr_pipeline.batch_export --docs 123,789 --share-root Z:/ --publish --ingest
  uv run python -m ocr_pipeline.batch_export --from-file docs.txt --publish --ingest --fail-fast
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .job_export import publish_and_ingest


def resolve_docs(docs: str | None, from_file: Path | None) -> list[str]:
    ids: list[str] = []
    if docs:
        ids.extend(x.strip() for x in docs.split(",") if x.strip())
    if from_file is not None:
        text = Path(from_file).read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ids.append(line)
    # Preserve order, drop duplicates
    seen: set[str] = set()
    out: list[str] = []
    for d in ids:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def resolve_artifact_stem(output_dir: Path, doc_id: str) -> str:
    """Prefer exact ``{doc_id}.txt``; else first ``{doc_id}.*.txt`` tagged stem."""
    exact = output_dir / f"{doc_id}.txt"
    if exact.is_file():
        return doc_id
    tagged = sorted(output_dir.glob(f"{doc_id}.*.txt"))
    # Prefer shortest tag (stable); skip nested weirdness
    candidates = [p for p in tagged if p.name.count(".") >= 2]
    if not candidates:
        raise FileNotFoundError(f"no output artifact for doc_id={doc_id!r} under {output_dir}")
    # stem of 123.got-ppocr.txt → 123.got-ppocr
    return candidates[0].name[: -len(".txt")]


def preflight(*, share_root: Path, do_publish: bool, do_ingest: bool) -> None:
    if do_publish:
        jobs = share_root / "jobs"
        try:
            jobs.mkdir(parents=True, exist_ok=True)
            probe = jobs / ".batch_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as e:
            raise SystemExit(f"share_root not writable: {share_root} ({e})") from e
    if do_ingest:
        key = os.environ.get("QDRANT_WRITER_KEY") or os.environ.get("QDRANT_API_KEY")
        if not key:
            raise SystemExit("Set QDRANT_WRITER_KEY (writer) before --ingest batch")


def run_batch(
    *,
    doc_ids: list[str],
    output_dir: Path,
    share_root: Path,
    do_publish: bool,
    do_ingest: bool,
    reindex: bool,
    fail_fast: bool,
    publish_and_ingest_fn=publish_and_ingest,
) -> list[tuple[str, str | None]]:
    """
    Returns list of (doc_id, error_message_or_None).
    """
    results: list[tuple[str, str | None]] = []
    for doc_id in doc_ids:
        try:
            stem = resolve_artifact_stem(output_dir, doc_id)
            publish_and_ingest_fn(
                output_dir=output_dir,
                artifact_stem=stem,
                doc_id=doc_id,
                share_root=share_root,
                source_pdf=f"{doc_id}.pdf",
                do_publish=do_publish,
                do_ingest=do_ingest,
                reindex=reindex,
            )
            results.append((doc_id, None))
            print(f"OK {doc_id} (stem={stem})")
        except Exception as e:  # noqa: BLE001 — per-doc isolation
            msg = f"{type(e).__name__}: {e}"
            print(f"FAIL {doc_id}: {msg}", file=sys.stderr)
            results.append((doc_id, msg))
            if fail_fast:
                break
    return results


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Batch stage→publish→ingest from output/")
    ap.add_argument("--docs", default=None, help="Comma-separated doc ids")
    ap.add_argument("--from-file", type=Path, default=None, help="One doc_id per line")
    ap.add_argument("--output-dir", type=Path, default=Path("output"))
    ap.add_argument("--share-root", type=Path, default=Path("Z:/"))
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after first doc failure (default: continue)",
    )
    return ap


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    doc_ids = resolve_docs(args.docs, args.from_file)
    if not doc_ids:
        raise SystemExit("Provide --docs and/or --from-file with at least one doc_id")
    if not args.publish and not args.ingest:
        raise SystemExit("Need --publish and/or --ingest")
    if args.ingest and not args.publish:
        raise SystemExit("Batch --ingest requires --publish (per-doc stage from output/)")

    preflight(share_root=args.share_root, do_publish=args.publish, do_ingest=args.ingest)
    results = run_batch(
        doc_ids=doc_ids,
        output_dir=args.output_dir,
        share_root=args.share_root,
        do_publish=args.publish,
        do_ingest=args.ingest,
        reindex=args.reindex,
        fail_fast=args.fail_fast,
    )
    failed = [d for d, err in results if err]
    if failed:
        raise SystemExit(f"batch finished with {len(failed)} failure(s): {', '.join(failed)}")
    print(f"batch OK: {len(results)} doc(s)")


if __name__ == "__main__":
    main()
