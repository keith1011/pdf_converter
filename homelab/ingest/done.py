"""DONE.json schema validation and hashing (Wave 1)."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

DONE_SCHEMA = 1
JOB_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_text(text: str) -> str:
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = unicodedata.normalize("NFKC", t)
    lines = [line.rstrip() for line in t.split("\n")]
    return "\n".join(lines)


def content_hash(text: str, tex: str | None = None) -> str:
    body = normalize_text(text) + "\n" + (tex or "")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _reject_path(rel: str) -> None:
    if not rel or rel.startswith("/") or rel.startswith("\\"):
        raise ValueError(f"invalid artifact path: {rel!r}")
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"path traversal not allowed: {rel!r}")


def validate_done_dict(data: dict[str, Any], job_dir: Path | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("DONE.json must be an object")
    extra = set(data) - {
        "done_schema",
        "job_id",
        "doc_id",
        "created_at",
        "source_pdf",
        "artifacts",
        "ocr_pipeline_version",
    }
    if extra:
        raise ValueError(f"unknown fields: {sorted(extra)}")

    if data.get("done_schema") != DONE_SCHEMA:
        raise ValueError(f"done_schema must be {DONE_SCHEMA}")

    job_id = data.get("job_id")
    if not isinstance(job_id, str) or not JOB_ID_RE.match(job_id):
        raise ValueError("invalid job_id")

    doc_id = data.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id or len(doc_id) > 128:
        raise ValueError("invalid doc_id")

    if not isinstance(data.get("created_at"), str) or not data["created_at"]:
        raise ValueError("created_at required")

    source_pdf = data.get("source_pdf")
    if not isinstance(source_pdf, str) or not source_pdf or "/" in source_pdf or "\\" in source_pdf:
        raise ValueError("source_pdf must be basename only")

    ocr_ver = data.get("ocr_pipeline_version")
    if not isinstance(ocr_ver, str) or not ocr_ver:
        raise ValueError("ocr_pipeline_version required")

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) < 1:
        raise ValueError("artifacts must be non-empty list")

    seen: set[str] = set()
    for i, art in enumerate(artifacts):
        if not isinstance(art, dict) or set(art) != {"path", "sha256"}:
            raise ValueError(f"artifacts[{i}] must be {{path, sha256}} only")
        rel = art["path"]
        digest = art["sha256"]
        if not isinstance(rel, str) or not isinstance(digest, str):
            raise ValueError(f"artifacts[{i}] types invalid")
        _reject_path(rel)
        if rel in seen:
            raise ValueError(f"duplicate artifact path: {rel}")
        seen.add(rel)
        if not SHA256_RE.match(digest):
            raise ValueError(f"artifacts[{i}].sha256 must be 64 lowercase hex")

    txt_name = f"{doc_id}.txt"
    if txt_name not in seen:
        raise ValueError(f"artifacts must include {txt_name}")

    if job_dir is not None:
        for art in artifacts:
            p = job_dir / art["path"]
            if not p.is_file():
                raise ValueError(f"missing file: {art['path']}")
            actual = sha256_file(p)
            if actual != art["sha256"]:
                raise ValueError(f"hash mismatch for {art['path']}: expected {art['sha256']}, got {actual}")
            # If pageir/tex exist on disk they must be listed
        for optional in (f"{doc_id}.pageir.json", f"{doc_id}.tex"):
            p = job_dir / optional
            if p.is_file() and optional not in seen:
                raise ValueError(f"{optional} exists on disk but not listed in artifacts")

    return data


def load_and_validate_done(job_dir: Path) -> dict[str, Any]:
    done_path = job_dir / "DONE.json"
    if not done_path.is_file():
        raise FileNotFoundError(f"missing DONE.json in {job_dir}")
    data = json.loads(done_path.read_text(encoding="utf-8"))
    return validate_done_dict(data, job_dir=job_dir)
