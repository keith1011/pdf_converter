"""Publish OCR artifacts to B Samba jobs/ with atomic DONE.json flow."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from homelab.ingest.done import sha256_file, validate_done_dict


def _git_sha(repo: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def publish(
    *,
    doc_id: str,
    source_dir: Path,
    share_root: Path,
    source_pdf: str | None = None,
    job_id: str | None = None,
) -> Path:
    source_dir = source_dir.resolve()
    share_root = share_root.resolve()
    pdf_name = source_pdf or f"{doc_id}.pdf"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_id = job_id or f"{stamp}-{doc_id}"

    required = [source_dir / f"{doc_id}.txt"]
    optional = [source_dir / f"{doc_id}.pageir.json", source_dir / f"{doc_id}.tex"]
    for p in required:
        if not p.is_file():
            raise FileNotFoundError(p)

    artifacts_src: list[Path] = list(required)
    for p in optional:
        if p.is_file():
            artifacts_src.append(p)

    incoming = share_root / "jobs" / ".incoming" / job_id
    final = share_root / "jobs" / job_id
    if final.exists():
        raise FileExistsError(f"job already published: {final}")
    if incoming.exists():
        shutil.rmtree(incoming)
    incoming.mkdir(parents=True)

    artifact_meta: list[dict[str, str]] = []
    for src in artifacts_src:
        dest = incoming / src.name
        shutil.copy2(src, dest)
        artifact_meta.append({"path": src.name, "sha256": sha256_file(dest)})

    # Nested figure crops: source_dir/figures/**/*.png → job figures/...
    figures_root = source_dir / "figures"
    if figures_root.is_dir():
        for png in sorted(figures_root.rglob("*.png")):
            rel = png.relative_to(source_dir).as_posix()
            dest = incoming / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(png, dest)
            artifact_meta.append({"path": rel, "sha256": sha256_file(dest)})

    # Verify hashes before DONE
    for art in artifact_meta:
        got = sha256_file(incoming / art["path"])
        if got != art["sha256"]:
            raise RuntimeError(f"copy hash mismatch: {art['path']}")

    # pageir crop_relpath must exist on disk
    pageir_path = incoming / f"{doc_id}.pageir.json"
    if pageir_path.is_file():
        pageir = json.loads(pageir_path.read_text(encoding="utf-8"))
        for page in pageir.get("pages", []):
            for seg in page.get("segments", []):
                rel = seg.get("crop_relpath")
                if not isinstance(rel, str) or not rel.strip():
                    continue
                crop = incoming / rel.strip()
                if not crop.is_file():
                    raise FileNotFoundError(
                        f"pageir lists crop_relpath={rel!r} but missing at publish: {crop}"
                    )

    done = {
        "done_schema": 1,
        "job_id": job_id,
        "doc_id": doc_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_pdf": Path(pdf_name).name,
        "artifacts": artifact_meta,
        "ocr_pipeline_version": _git_sha(
            source_dir.parent if (source_dir.parent / ".git").exists() else Path.cwd()
        ),
    }
    validate_done_dict(done, job_dir=incoming)

    done_path = incoming / "DONE.json"
    done_path.write_text(json.dumps(done, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Atomic-ish publish: rename incoming → jobs/<id>
    final.parent.mkdir(parents=True, exist_ok=True)
    incoming.rename(final)
    return final


def main() -> None:
    ap = argparse.ArgumentParser(description="Publish OCR outputs as a DONE job on Samba share")
    ap.add_argument("--doc-id", required=True)
    ap.add_argument("--source-dir", type=Path, default=Path("output"))
    ap.add_argument(
        "--share-root",
        type=Path,
        default=Path("Z:/"),
        help="Mapped Samba root (contains jobs/)",
    )
    ap.add_argument("--source-pdf", default=None)
    ap.add_argument("--job-id", default=None)
    args = ap.parse_args()
    dest = publish(
        doc_id=args.doc_id,
        source_dir=args.source_dir,
        share_root=args.share_root,
        source_pdf=args.source_pdf,
        job_id=args.job_id,
    )
    print(f"PUBLISHED {dest}")


if __name__ == "__main__":
    main()
