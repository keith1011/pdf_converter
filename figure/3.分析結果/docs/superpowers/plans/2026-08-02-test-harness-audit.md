# Figure Test Harness Audit Plan

> **For agentic workers:** This is a read-only audit plan. Do not merge a
> temporary harness into the permanent test suite.

**Goal:** Audit the test harness referenced by the current project TODO and
record whether it exists, how the repository actually runs tests, and whether
the Figure test suite has a safe reproducible collection and execution path.

**Architecture:** Treat `test/2_生產線/tests/__mkdir_tmp__-test).ts` as an explicitly
named candidate harness, then compare it with the repository's actual Python
`pytest` configuration. The audit produces a report only; it does not add test
files, alter pytest configuration, or promote temporary code.

**Tech Stack:** PowerShell, Python 3.12, `uv`, `pytest`, repository
`pytest.ini`／`pyproject.toml` configuration.

---

### Task 1: Locate the named harness and map the permanent runner

**Files:**

- Read: `AGENTS.md`
- Read: `pytest.ini`
- Read: `pyproject.toml`
- Inspect: `test/`, `2_生產線/tests/`, `_opencode_export/`

- [ ] **Step 1: Check the exact TODO target**

Run:

```powershell
Test-Path -LiteralPath 'test/2_生產線/tests/__mkdir_tmp__-test).ts'
Test-Path -LiteralPath 'test'
Test-Path -LiteralPath 'tests'
```

Expected audit result: the named TypeScript path is absent; the existing
permanent test root is `2_生產線/tests/`.

- [ ] **Step 2: Inspect runner configuration**

Run:

```powershell
Get-Content -LiteralPath 'pytest.ini' -Encoding UTF8
Select-String -LiteralPath 'pyproject.toml' -Pattern '\[tool.pytest.ini_options\]|pythonpath|testpaths'
```

Record the effective test root, import path and markers in the report.

### Task 2: Verify collection and Figure test execution

**Files:**

- Read-only execution: `2_生產線/tests/figure_pipeline/`
- Temporary output: `.pytest-tmp-local/figure-harness-audit/`

- [ ] **Step 1: Collect the permanent suite without cache writes**

Run:

```powershell
uv run python -m pytest --collect-only -q -p no:cacheprovider `
  --basetemp .pytest-tmp-local/figure-harness-audit-collect
```

Expected: collection completes without importing a TypeScript harness and
reports the collected Python tests.

- [ ] **Step 2: Run the isolated Figure suite**

Run:

```powershell
uv run python -m pytest 2_生產線/tests/figure_pipeline -q -p no:cacheprovider `
  --basetemp .pytest-tmp-local/figure-harness-audit-figure
```

Expected: all existing Figure tests pass; record the exact count and exit code.

### Task 3: Publish the audit report without suite changes

**Files:**

- Create: `3.分析結果/docs/figure_pipeline/test-harness-audit.md`
- Do not modify: `2_生產線/tests/**`, `pytest.ini`, `pyproject.toml`,
  `2_生產線/src/figure_pipeline/**`

- [ ] **Step 1: Record findings and disposition**

The report must state:

1. The named TypeScript harness path is absent and cannot be merged as-is.
2. The permanent harness is Python `pytest` rooted at `2_生產線/tests/`.
3. The effective `pythonpath`, test root and marker configuration.
4. Collection and Figure-suite command results.
5. A disposition: keep the TODO open until the missing harness is located or
   its owner supplies it; do not add a speculative replacement.

- [ ] **Step 2: Confirm no permanent suite mutation**

Run:

```powershell
git status --short --untracked-files=all -- tests pytest.ini pyproject.toml 2_生產線/src/figure_pipeline
```

Expected: no modified or newly created test／production files attributable to
this audit; only the audit plan/report may be new.
