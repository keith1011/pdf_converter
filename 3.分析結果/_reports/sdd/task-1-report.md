# Task 1 Report: PageIR figure model + render + JSON field

**Date:** 2026-07-24  
**Status:** DONE  
**Scope:** `models.py`, `content_first.py`, `tests/test_page_ir_models.py`, `tests/test_content_first.py`

## Summary

Extended PageIR with `SegmentKind.FIGURE`, optional `ContentSegment.crop_relpath`, figure caption rendering `(圖: {text})`, and JSON serialization of `crop_relpath`. No router/pipeline/publish/ingest changes.

## Changes

### `src/ocr_pipeline/models.py`

- Added `SegmentKind.FIGURE = "figure"` to `SegmentKind` enum.
- Added `crop_relpath: str | None = None` field to `ContentSegment` dataclass.

### `src/ocr_pipeline/content_first.py`

- `render_page_ir`: new branch for `SegmentKind.FIGURE` → `(圖: {seg.text})`.
- `write_pageir_json`: segment dict now includes `"crop_relpath": s.crop_relpath`.
- `apply_integrity_to_page`: MATH rebuild passes through `crop_relpath=seg.crop_relpath`.

## TDD Evidence

### RED — failing tests (Step 2)

**Command:**
```bash
uv run pytest tests/test_page_ir_models.py::test_content_segment_figure_has_crop_relpath tests/test_content_first.py::test_render_figure_as_caption_stub tests/test_content_first.py::test_write_pageir_json_includes_crop_relpath -q
```

**Output:**
```
FFF                                                                      [100%]
================================== FAILURES ===================================
________________ test_content_segment_figure_has_crop_relpath _________________
E       AttributeError: type object 'SegmentKind' has no attribute 'FIGURE'
_____________________ test_render_figure_as_caption_stub ______________________
E       AttributeError: type object 'SegmentKind' has no attribute 'FIGURE'
________________ test_write_pageir_json_includes_crop_relpath _________________
E       AttributeError: type object 'SegmentKind' has no attribute 'FIGURE'
3 failed in 1.37s
```

**Root cause:** `SegmentKind.FIGURE` and `ContentSegment.crop_relpath` did not exist; render/JSON paths had no figure handling.

### GREEN — full suite (Step 4)

**Command:**
```bash
uv run pytest tests/test_page_ir_models.py tests/test_content_first.py -q
```

**Output:**
```
...........                                                              [100%]
11 passed in 1.41s
```

## Self-Review

| Check | Result |
|-------|--------|
| TDD order (RED → implement → GREEN) | ✓ |
| Minimal diff; no router/pipeline touch | ✓ |
| Default `crop_relpath=None` backward-compatible | ✓ |
| Existing segmenter call sites unchanged (later tasks wire FIGURE) | ✓ |
| Linter clean on modified source files | ✓ |
| Commit skipped per instructions | ✓ |

## Concerns

None. `write_pageir_json` emits `"crop_relpath": null` for segments without a crop path; acceptable for JSON round-trip and matches dataclass default.

## Commits

None (as instructed).
