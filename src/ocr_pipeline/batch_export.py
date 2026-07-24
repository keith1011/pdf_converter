"""Batch stage / publish / ingest OCR output docs."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from .job_stage import stage_job_dir

# Monkeypatch targets for tests; homelab imports happen lazily in main/run_batch.
publish: Callable[..., Path] | None = None
ingest_job: Callable[..., tuple[int, int]] | None = None


def _import_homelab() -> tuple[Callable[..., Path], Callable[..., tuple[int, int]]]:
    root = Path(__file__).resolve().parents[2]
    ingest_dir = root / "homelab" / "ingest"
    if str(ingest_dir) not in sys.path:
        sys.path.insert(0, str(ingest_dir))
    from ingest import ingest_job as _ingest_job  # type: ignore
    from publish import publish as _publish  # type: ignore

    return _publish, _ingest_job


def preflight(*, share_root: Path, do_publish: bool, do_ingest: bool, api_key: str | None) -> None:
    if do_ingest and not do_publish:
        raise SystemExit("--ingest requires --publish in this milestone")
    if do_publish:
        jobs = share_root / "jobs"
        jobs.mkdir(parents=True, exist_ok=True)
        probe = jobs / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    if do_ingest and not api_key:
        raise SystemExit("Set --api-key or QDRANT_WRITER_KEY before --ingest")


def run_batch(
    *,
    doc_ids: list[str],
    output_dir: Path,
    share_root: Path,
    do_publish: bool,
    do_ingest: bool,
    fail_fast: bool,
    staging_root: Path,
    qdrant_url: str,
    api_key: str | None,
    reindex: bool,
) -> int:
    global publish, ingest_job

    pub: Any = publish
    ing: Any = ingest_job
    if (do_publish or do_ingest) and (pub is None or ing is None):
        pub, ing = _import_homelab()
        publish, ingest_job = pub, ing

    failures = 0
    for doc_id in doc_ids:
        try:
            staging = staging_root / doc_id
            stage_job_dir(doc_id=doc_id, output_dir=output_dir, staging_dir=staging)
            job_dir = None
            if do_publish:
                job_dir = pub(
                    doc_id=doc_id,
                    source_dir=staging,
                    share_root=share_root,
                )
                print(f"PUBLISHED {doc_id} -> {job_dir}")
            if do_ingest:
                if job_dir is None:
                    raise RuntimeError("--ingest requires --publish in this milestone")
                n, total = ing(
                    job_dir,
                    qdrant_url=qdrant_url,
                    api_key=api_key or "",
                    reindex=reindex,
                )
                print(f"INGESTED {doc_id} {n}/{total}")
        except (Exception, SystemExit) as exc:  # noqa: BLE001
            failures += 1
            print(f"ERROR {doc_id}: {exc}")
            if fail_fast:
                return 1
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    global publish, ingest_job

    ap = argparse.ArgumentParser(description="Batch stage/publish/ingest OCR output docs")
    ap.add_argument("--docs", default="", help="Comma-separated doc ids")
    ap.add_argument("--from-file", type=Path, default=None)
    ap.add_argument("--output-dir", type=Path, default=Path("output"))
    ap.add_argument("--share-root", type=Path, default=Path("Z:/"))
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL", "http://192.168.1.107:6333"))
    ap.add_argument("--api-key", default=os.environ.get("QDRANT_WRITER_KEY") or os.environ.get("QDRANT_API_KEY"))
    ap.add_argument("--staging-root", type=Path, default=None)
    args = ap.parse_args(argv)

    doc_ids: list[str] = []
    if args.docs:
        doc_ids.extend([d.strip() for d in args.docs.split(",") if d.strip()])
    if args.from_file:
        doc_ids.extend(
            [
                line.strip()
                for line in args.from_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        )
    if not doc_ids:
        raise SystemExit("Provide --docs or --from-file")

    if args.publish or args.ingest:
        publish, ingest_job = _import_homelab()

    staging_root = args.staging_root or Path(tempfile.mkdtemp(prefix="pocr-stage-"))
    preflight(
        share_root=args.share_root,
        do_publish=args.publish,
        do_ingest=args.ingest,
        api_key=args.api_key,
    )
    return run_batch(
        doc_ids=doc_ids,
        output_dir=args.output_dir,
        share_root=args.share_root,
        do_publish=args.publish,
        do_ingest=args.ingest,
        fail_fast=args.fail_fast,
        staging_root=staging_root,
        qdrant_url=args.qdrant_url,
        api_key=args.api_key,
        reindex=args.reindex,
    )


if __name__ == "__main__":
    raise SystemExit(main())
