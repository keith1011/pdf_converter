# Task 2 Report: Figure caption prompt + `figure_export` helper

**Date:** 2026-07-24  
**Status:** DONE  
**Commits:** none (per instructions)

## Goal

Add `FIGURE_CAPTION_PROMPT` and `export_figures()` helper that crops FIGURE blocks to PNG, calls VLM for a one-line Traditional Chinese caption, and returns `ContentSegment` rows with `crop_relpath`. Pipeline/factory wiring deferred to Task 3.

## TDD Steps

| Step | Action | Result |
|------|--------|--------|
| 1 | Wrote `tests/test_figure_export.py` (exact brief) | — |
| 2 | `uv run pytest tests/test_figure_export.py -q` | **FAIL** — `ModuleNotFoundError: ocr_pipeline.figure_export` |
| 3 | Added `FIGURE_CAPTION_PROMPT` to `prompts.py`; created `figure_export.py` | — |
| 4 | Re-ran pytest | **PASS** — 2 passed in 1.34s |

## Files Changed

| File | Change |
|------|--------|
| `src/ocr_pipeline/prompts.py` | Added `FIGURE_CAPTION_PROMPT` (Traditional Chinese one-line caption rules) |
| `src/ocr_pipeline/figure_export.py` | New: `_ensure_crop()`, `export_figures()` |
| `tests/test_figure_export.py` | New: success + VLM failure isolation tests |

## Interfaces Delivered

- **`FIGURE_CAPTION_PROMPT: str`** — prompt for Qwen/VLM figure captioning
- **`export_figures(*, blocks, figures_dir, vlm, max_new_tokens=128) -> tuple[list[ContentSegment], list[str]]`**
  - Filters `BlockType.FIGURE` only
  - Writes `figures_dir / f"{block.block_id}.png"` (crop from page or copy existing `crop_path`)
  - Calls `vlm.generate(FIGURE_CAPTION_PROMPT, image_path=..., max_new_tokens=...)`
  - Returns segments with `kind=FIGURE`, caption text, `crop_relpath=f"figures/{block_id}.png"`
  - Per-figure failures → warning `figure {block_id}: {exc}`, no segment

## Test Summary

```
uv run pytest tests/test_figure_export.py -q
..                                                                       [100%]
2 passed in 1.34s
```

- `test_export_figures_writes_png_and_segment` — crop PNG written, segment fields correct, no warnings
- `test_export_figures_skips_failed_caption` — VLM exception → empty segments, warning contains block id

## Dependencies on Task 1

Uses existing:
- `SegmentKind.FIGURE`
- `ContentSegment.crop_relpath`
- `LayoutBlock` with `bbox`, `image_path`, optional `crop_path`
- `BBox.clamp()` / `as_int_tuple()`

## Out of Scope (Task 3)

- Pipeline integration
- Factory/router wiring
- Content-first segment merge from exported figures

## Concerns / Notes

- **No GPU smoke:** tests use `FakeVlm` / `BoomVlm`; real Qwen caption quality not validated here.
- **Broad except:** `export_figures` catches all exceptions per figure (intentional isolation per brief); empty caption treated as failure.
- **PIL lazy import:** `_ensure_crop` imports PIL inside function when cropping from page (matches brief).
- **Non-FIGURE blocks:** silently skipped (no warning).

## Verification Commands

```powershell
uv run pytest tests/test_figure_export.py -q
```

## Next

Task 3: wire `export_figures` into pipeline/factory and merge FIGURE segments into PageIR/content-first flow.
