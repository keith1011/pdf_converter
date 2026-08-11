### Task 6: Batch CLI `ocr_pipeline.batch_export`

**Files:**
- Create: `src/ocr_pipeline/batch_export.py`
- Test: `tests/test_batch_export.py`

**Interfaces:**
- Produces module CLI:
  - `uv run python -m ocr_pipeline.batch_export --docs 123,789 --output-dir output --share-root Z:/ --publish --ingest`
  - `--from-file docs.txt` (one doc_id per line)
  - `--fail-fast`
  - `--reindex` passed to ingest
  - Preflight: `share_root/jobs` writable; `QDRANT_WRITER_KEY` or `--api-key` if `--ingest`
  - Per doc: `stage_job_dir` → `publish` → `ingest_job`
  - On error: log `doc_id` + exception; continue unless `--fail-fast`
  - Exit code 1 if any doc failed

- [ ] **Step 1: Write failing test**

```python
# tests/test_batch_export.py
from __future__ import annotations

from pathlib import Path

from ocr_pipeline.batch_export import run_batch


def test_batch_continues_after_one_failure(tmp_path: Path, monkeypatch):
    calls: list[str] = []

    def fake_stage(*, doc_id, output_dir, staging_dir):
        calls.append(f"stage:{doc_id}")
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / f"{doc_id}.txt").write_text("x", encoding="utf-8")
        return staging_dir

    def fake_publish(**kwargs):
        doc_id = kwargs["doc_id"]
        calls.append(f"publish:{doc_id}")
        if doc_id == "bad":
            raise RuntimeError("boom")
        return tmp_path / "jobs" / doc_id

    def fake_ingest(job_dir, **kwargs):
        calls.append(f"ingest:{job_dir.name}")
        return 1, 1

    monkeypatch.setattr("ocr_pipeline.batch_export.stage_job_dir", fake_stage)
    monkeypatch.setattr("ocr_pipeline.batch_export.publish", fake_publish)
    monkeypatch.setattr("ocr_pipeline.batch_export.ingest_job", fake_ingest)

    rc = run_batch(
        doc_ids=["bad", "good"],
        output_dir=tmp_path / "output",
        share_root=tmp_path / "Z",
        do_publish=True,
        do_ingest=True,
        fail_fast=False,
        staging_root=tmp_path / "staging",
        qdrant_url="http://example",
        api_key="k",
        reindex=False,
    )
    assert rc == 1
    assert calls == [
        "stage:bad",
        "publish:bad",
        "stage:good",
        "publish:good",
        "ingest:good",
    ]
```

Note: adjust expected call list if ingest is skipped when publish fails (correct behavior: no ingest after failed publish).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_batch_export.py -q`

Expected: FAIL (module missing)

- [ ] **Step 3: Minimal implementation**

```python
# src/ocr_pipeline/batch_export.py
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from .job_stage import stage_job_dir


def _import_homelab():
    root = Path(__file__).resolve().parents[2]
    ingest_dir = root / "homelab" / "ingest"
    if str(ingest_dir) not in sys.path:
        sys.path.insert(0, str(ingest_dir))
    from ingest import ingest_job  # type: ignore
    from publish import publish  # type: ignore

    return publish, ingest_job


publish, ingest_job = _import_homelab()  # noqa: E305 — lazy at import for tests to monkeypatch


def preflight(*, share_root: Path, do_publish: bool, do_ingest: bool, api_key: str | None) -> None:
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
    failures = 0
    for doc_id in doc_ids:
        try:
            staging = staging_root / doc_id
            stage_job_dir(doc_id=doc_id, output_dir=output_dir, staging_dir=staging)
            job_dir = None
            if do_publish:
                job_dir = publish(
                    doc_id=doc_id,
                    source_dir=staging,
                    share_root=share_root,
                )
                print(f"PUBLISHED {doc_id} -> {job_dir}")
            if do_ingest:
                if job_dir is None:
                    raise RuntimeError("--ingest requires --publish in this milestone")
                n, total = ingest_job(
                    job_dir,
                    qdrant_url=qdrant_url,
                    api_key=api_key or "",
                    reindex=reindex,
                )
                print(f"INGESTED {doc_id} {n}/{total}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"ERROR {doc_id}: {exc}")
            if fail_fast:
                return 1
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
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
```

Fix import pattern so tests can monkeypatch `ocr_pipeline.batch_export.publish` — prefer importing inside `run_batch` from module globals that tests patch:

```python
# at module level after defining run_batch helpers:
from ocr_pipeline.job_stage import stage_job_dir as stage_job_dir  # already

# In run_batch, use globals:
# publish / ingest_job assigned in main via _import_homelab, default None
publish = None
ingest_job = None
```

Implementer: ensure `test_batch_export` monkeypatches work; call `_import_homelab()` only in `main()`, and in `run_batch` use:

```python
    pub = publish
    ing = ingest_job
    if pub is None or ing is None:
        pub, ing = _import_homelab()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_batch_export.py tests/test_job_stage.py tests/test_ingest_figures.py tests/test_figure_export.py tests/test_content_first.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add src/ocr_pipeline/batch_export.py tests/test_batch_export.py
git commit -m "feat: batch stage/publish/ingest CLI"
```

---
