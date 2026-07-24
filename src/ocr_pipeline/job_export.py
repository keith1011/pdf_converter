"""Stage OCR artifacts for DONE publish and optional Qdrant ingest."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def stage_job_artifacts(
    *,
    output_dir: Path,
    artifact_stem: str,
    doc_id: str,
) -> Path:
    """
    Copy ``{artifact_stem}.{txt,tex,pageir.json}`` into
    ``output_dir/.publish_stage/{doc_id}/{doc_id}.*`` for Homelab publish.

    Tagged OCR outputs (e.g. ``123.got-ppocr``) keep their originals; only
    copies are renamed to the publish ``doc_id`` contract.
    """
    output_dir = Path(output_dir)
    txt_src = output_dir / f"{artifact_stem}.txt"
    if not txt_src.is_file():
        raise FileNotFoundError(f"required artifact missing: {txt_src}")

    stage_dir = output_dir / ".publish_stage" / doc_id
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    shutil.copy2(txt_src, stage_dir / f"{doc_id}.txt")
    for suffix in (".tex", ".pageir.json"):
        src = output_dir / f"{artifact_stem}{suffix}"
        if src.is_file():
            shutil.copy2(src, stage_dir / f"{doc_id}{suffix}")
    return stage_dir


def publish_and_ingest(
    *,
    output_dir: Path,
    artifact_stem: str,
    doc_id: str,
    share_root: Path,
    source_pdf: str | None = None,
    do_publish: bool = True,
    do_ingest: bool = False,
    job_dir: Path | None = None,
    reindex: bool = False,
    qdrant_url: str | None = None,
    api_key: str | None = None,
) -> tuple[Path | None, int | None, int | None]:
    """
    Stage → publish (optional) → ingest (optional).

    Returns ``(job_dir, upserted, total)``. Upsert counts are None when ingest
    is skipped. Raises ``SystemExit`` with a clear message when env/share is
    missing for the requested steps.
    """
    published: Path | None = job_dir
    upserted: int | None = None
    total: int | None = None

    if do_publish:
        stage = stage_job_artifacts(
            output_dir=output_dir,
            artifact_stem=artifact_stem,
            doc_id=doc_id,
        )
        share_root = Path(share_root)
        jobs_parent = share_root / "jobs"
        try:
            jobs_parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise SystemExit(
                f"Cannot write share_root={share_root} (is Z: mapped?): {e}"
            ) from e

        from homelab.ingest.publish import publish

        published = publish(
            doc_id=doc_id,
            source_dir=stage,
            share_root=share_root,
            source_pdf=source_pdf or f"{doc_id}.pdf",
        )
        print(f"PUBLISHED {published}")

    if do_ingest:
        if published is None:
            raise SystemExit("--ingest requires --publish or --job-dir")
        key = api_key or os.environ.get("QDRANT_WRITER_KEY") or os.environ.get("QDRANT_API_KEY")
        if not key:
            raise SystemExit("Set --api-key or QDRANT_WRITER_KEY to the writer key")
        url = qdrant_url or os.environ.get("QDRANT_URL", "http://192.168.1.107:6333")

        from homelab.ingest.ingest import COLLECTION, ingest_job

        upserted, total = ingest_job(
            Path(published),
            qdrant_url=url,
            api_key=key,
            reindex=reindex,
        )
        print(f"UPSERTED {upserted}/{total} points into {COLLECTION}")

    return published, upserted, total
