# Task 6 Report: Batch CLI `ocr_pipeline.batch_export`

**Status:** DONE  
**Commits:** none (not requested)

## What shipped

- `src/ocr_pipeline/batch_export.py` — CLI `python -m ocr_pipeline.batch_export`
  - `--docs` / `--from-file`, `--publish`, `--ingest`, `--fail-fast`, `--reindex`
  - Preflight: `share_root/jobs` writable; API key required when `--ingest`
  - Per doc: `stage_job_dir` → `publish` → `ingest_job`
  - Failures logged; continue unless `--fail-fast`; exit 1 if any failed
  - `--ingest` without successful publish path raises (milestone requires `--publish`)
- Module-level `publish` / `ingest_job` / `stage_job_dir` are monkeypatchable; homelab import is lazy (`main` / first `run_batch` use)

## Tests

```text
uv run pytest tests/test_batch_export.py tests/test_job_stage.py tests/test_ingest_figures.py tests/test_figure_export.py tests/test_content_first.py -q
15 passed in 2.08s
```

TDD: RED = `ModuleNotFoundError: ocr_pipeline.batch_export` → GREEN after implement.

## Concerns

- No dedicated CLI/preflight unit tests yet (only continue-after-failure path).
- Homelab `publish`/`ingest_job` only loaded when publish/ingest requested; stage-only runs never import them.

## Fix (2026-07-24): SystemExit per-doc + ingest preflight

**Important #1:** `homelab/ingest/ingest.py` can raise `SystemExit` (empty segments / missing fastembed). Per-doc `except Exception` did not catch it, aborting the whole batch.

- Changed per-doc handler to `except (Exception, SystemExit) as exc:` so batch logs `ERROR {doc_id}` and continues (unless `--fail-fast`).
- Added `test_batch_continues_after_ingest_systemexit`: first doc `ingest_job` → `SystemExit("no segments")` after publish; second doc still stage+publish+ingest; `rc == 1`.

**Important #2 (cheap):** `preflight` now rejects `--ingest` without `--publish` with `SystemExit("--ingest requires --publish in this milestone")`.

### Verification

```text
uv run pytest tests/test_batch_export.py -q
..                                                                       [100%]
2 passed in 1.58s
```

No commit (not requested).
