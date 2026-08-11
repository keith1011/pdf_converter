# Task 5 Report: Ingest pageir_v2 + crop_path payload

## Status

DONE

## Changes

- Bumped `CHUNK_VERSION` from `pageir_v1` to `pageir_v2` in `homelab/ingest/ingest.py`.
- Extended `load_segments` so PageIR `crop_relpath` is mapped onto segment dicts as `crop_path` when present.
- Extended `ingest_job` Qdrant payload construction to include `crop_path` only when the segment has it (figures with crops; omitted for prose/other).
- Added `tests/test_ingest_figures.py` covering version bump and crop_path mapping.

## TDD and verification

- RED: `uv run pytest tests/test_ingest_figures.py -q` → 2 failed (`pageir_v1` assertion; missing `crop_path` KeyError).
- GREEN: `uv run pytest tests/test_ingest_figures.py -q` → 2 passed.

## Commits

None, as requested.

## Concerns

- `CHUNK_VERSION` participates in `point_id` UUID5 keys, so re-ingest after this change will write new point IDs for the same doc/page/segment. Existing `pageir_v1` points are not deleted unless `--reindex` is used.
- Brief tests cover `load_segments` + version only; payload omit/include for non-figures is implemented but not unit-tested separately.
