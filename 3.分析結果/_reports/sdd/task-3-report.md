# Task 3 Report — Router crops FIGURE; finalize merges figure segments

## Status

DONE. No git commit was created, as requested.

## Implementation

- `DynamicRouter` now always crops FIGURE blocks. With `skip_figures=True`, it keeps `raw_text=""`, sets `meta["skipped"]=True` and `meta["skip_reason"]="skip_figures"`, and does not call the text OCR engine.
- `finalize_content_first` accepts `figure_segments_by_page` and appends matching FIGURE segments before document rendering and PageIR serialization.
- `PipelineManager` collects routed FIGURE blocks, calls `export_figures` after polish, writes crops under `output_dir/<artifact_source>/figures`, groups returned segments by page, forwards exporter warnings, and passes the groups into finalization.
- `PipelineManager.extract_figures` defaults to `True`; factory reads `pipeline.extract_figures`.
- `config/ocr_pipeline.yaml` documents the revised `skip_figures` behavior and enables `extract_figures: true`.

## Tests changed

- Replaced the old skip-without-crop router expectation with crop-but-no-OCR.
- Added finalizer FIGURE merge coverage.
- Added factory `extract_figures` default/override coverage.
- Added pipeline integration coverage for export destination and PageIR merge.

## TDD evidence

Initial RED command:

`uv run pytest tests/test_skip_figures_router.py::test_skip_figures_true_crops_but_does_not_ocr tests/test_content_first.py::test_finalize_merges_figure_segments -q`

Result: 2 failed as expected:

1. skipped FIGURE had `crop_path=None`;
2. `finalize_content_first` rejected `figure_segments_by_page`.

After implementation:

- Focused RED-to-GREEN tests: 2 passed.
- Required related suite: 16 passed.
- Pipeline integration file: 2 passed.
- Full suite: 135 passed, 1 warning.
- Ruff on all changed Python files: clean.
- IDE diagnostics on changed files: none.

## Concerns

- No real GPU/VLM OCR run was performed; exporter integration is covered with a deterministic test double.
- The only full-suite warning is an existing third-party Surya/Pydantic deprecation warning.
