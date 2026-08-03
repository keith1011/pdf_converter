# Test Harness Audit

Date: 2026-08-02

## Scope

This audit covers the TODO in `AGENTS.md`:

```text
test/tests/__mkdir_tmp__-test).ts
```

The audit is read-only with respect to the permanent test suite. No temporary
TypeScript harness was added, and no pytest configuration, production source or
existing test file was changed.

## Findings

### Named harness

- `test/` does not exist.
- `test/tests/__mkdir_tmp__-test).ts` does not exist.
- `_opencode_export/pdf-scaner-opencode/test/tests/__mkdir_tmp__-test).ts` also
  does not exist.
- No TypeScript／TSX／JavaScript harness matching the TODO was found in the
  workspace outside the copied `_opencode_export` snapshot.

The TODO therefore cannot be audited by execution. There is no concrete file to
merge into the permanent suite.

### Permanent runner

The repository's actual test harness is Python `pytest`:

- `pytest.ini`: `pythonpath = src`, `testpaths = tests`.
- `pyproject.toml`: repeats `pythonpath = ["src"]` and `testpaths = ["tests"]`.
- `2_生產線/tests/figure_pipeline/` is the isolated Figure test root.

## Execution evidence

### Full collection

Command:

```powershell
uv run python -m pytest --collect-only -q -p no:cacheprovider `
  --basetemp .pytest-tmp-local/figure-harness-audit-collect
```

Result:

```text
298 tests collected, 2 errors in 7.56s
```

The errors are:

- `2_生產線/tests/test_ingest_figures.py`
- `2_生產線/tests/test_ingest_quality_gate.py`

Both fail during import because `2_生產線/homelab/ingest/ingest.py` imports the missing
optional dependency `qdrant_client`:

```text
ModuleNotFoundError: No module named 'qdrant_client'
```

This is a permanent-suite collection failure, not a Figure B1 failure.

### Figure-only suite

Command:

```powershell
uv run python -m pytest 2_生產線/tests/figure_pipeline -q -p no:cacheprovider `
  --basetemp .pytest-tmp-local/figure-harness-audit-figure
```

Result:

```text
19 passed in 1.76s
```

## Disposition

1. Keep the named harness TODO open until its owner supplies the missing file or
   corrects the path.
2. Do not create a speculative TypeScript replacement.
3. Treat the missing `qdrant_client` dependency as an upstream/full-suite
   harness issue; resolve it separately from Track B Figure work.
4. Figure B1's isolated test entry point is currently reproducible and green.

## Scope check

No files under `2_生產線/tests/`, `pytest.ini`, `pyproject.toml` or
`2_生產線/src/figure_pipeline/` were changed by this audit. Temporary pytest output was
written only under `.pytest-tmp-local/`.
