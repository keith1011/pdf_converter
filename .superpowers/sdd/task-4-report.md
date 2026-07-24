# Task 4 Report: Job staging + publish figures

## Status

DONE

## Changes

- Added `stage_job_dir()` to recreate a clean staging directory and copy required text, optional TeX/PageIR, and PNG figures.
- Extended `publish()` to discover staged `figures/*.png`, preserve relative paths, create nested destinations, and record relative paths in `DONE.json`.
- Extended DONE validation so every on-disk `figures/*.png` must be listed in artifacts.
- Added staging, publish, listed-figure, and unlisted-figure regression tests.

## TDD and verification

- RED: collection failed with `ModuleNotFoundError: ocr_pipeline.job_stage`.
- Focused: `uv run pytest tests/test_job_stage.py tests/test_done_schema.py tests/test_publish_figures.py -q` → 9 passed.
- Full: `uv run pytest -q` → 140 passed, 1 third-party Surya/Pydantic deprecation warning.
- Lint: scoped `uv run ruff check ...` → all checks passed.

## Commits

None, as requested.

## Concerns

None. Figure discovery intentionally follows the brief's direct `figures/*.png` contract rather than recursive nested directories.
