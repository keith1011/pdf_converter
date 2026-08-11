# Figure Pipeline Integration Design

**Date:** 2026-08-10  
**Status:** Approved architecture (方案 A)  
**Target repository:** `pdf_scaner`

## Goal

Integrate the reviewed Figure B1/B2/B3 workflow into the existing P-ocr repository as
one operational system while preserving the locked OCR contract. OCR text and figure
assets share the same Stage1 question identity, configuration, local Qwen client, output
root, and final PageIR assembly, but figure classification and visible-label OCR remain
explicitly human-gated.

## Non-goals

- Do not change the DSE Paper 2 one-question-per-crop regioner.
- Do not replace PaddleOCR-VL as Stage2 primary text OCR.
- Do not add a Stage3 VLM rewrite; MCQ Stage3 remains deterministic `sanitize`.
- Do not enable `nup` or `structured_ocr`.
- Do not call an external or paid Vision API.
- Do not run GPU OCR while performing the repository integration.
- Do not overwrite or delete existing output, layout, crop, cache, or review bundles.
- Do not make the legacy automatic caption exporter authoritative for reviewed figures.

## Accepted Source Package

The accepted handoff is the `files/` tree under
`figure/3.分析結果/reports/main_figure_integration_2026-08-10`.

The package contains 64 files, including 24 Figure runtime modules, 19 test modules
(125 test functions), four command wrappers, configuration additions, and supporting
documentation. The supplied `SHA256SUMS.txt` is stale: 44 differences are newline-only,
and the remaining seven package files match the current Figure source workspace byte for
byte. Integration therefore treats the current `files/` tree as the source of truth and
generates a new target-side import manifest after relocation.

## Repository Layout

Runtime paths remain at repository root as required by `AGENTS.md`:

```text
src/
  ocr_pipeline/                 existing OCR system
  figure_pipeline/              imported B1/B2/B3 implementation
tests/
  figure_pipeline/              imported Figure tests
scripts/
  run_figure_pipeline.py        unified workflow entrypoint
  phase_b1_figure_asset.py      compatibility wrapper
  phase_b2_figure_classify.py   compatibility wrapper
  phase_b3_visible_labels.py    compatibility wrapper
  evaluate_b3_sequence_order.py compatibility wrapper
config/
  ocr_pipeline.yaml             shared OCR + Figure configuration
output/
  figure_pipeline/              immutable workflow bundles
3.分析結果/
  docs/figure_pipeline/         imported operational documentation
  reports/figure_integration/   regenerated import manifest and verification report
```

The incoming shared `pyproject.toml`, `pytest.ini`, `.python-version`, `uv.lock`, and full
OCR configuration are not copied over the target files. Their relevant deltas are merged.

## Packaging and Environment

Hatchling packages both top-level Python packages:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/ocr_pipeline", "src/figure_pipeline"]
```

The machine currently has Python 3.12.10, but no `uv`; the old `.venv` points to the
pre-reinstall Python location and cannot start. Bootstrap `uv` into a writable user data
location, then set `UV_PROJECT_ENVIRONMENT=.venv-rebuilt` and restore from `uv.lock`.
The stale `.venv` is retained until the rebuilt environment passes the focused baseline.
All verification commands use `--locked` until an intentional dependency metadata change
requires a lock refresh.

## Shared Configuration

Merge only these Figure sections into `config/ocr_pipeline.yaml`:

```yaml
figure_classification:
  enabled: true
  max_new_tokens: 256
  prompt_version: "figure-b2-v1"

figure_label_ocr:
  enabled: true
  max_new_tokens: 384
  prompt_version: "figure-b3-v3"
```

The target OCR engine, paths, quality, `nup`, `structured_ocr`, and Stage3 settings remain
unchanged. Figure commands use the existing `ocr_pipeline.factory.load_ocr_config` and
`build_vlm_client`, so Qwen must have a non-empty `model_name` and
`load_in_4bit: true`.

## Workflow and Human Gates

The unified entrypoint exposes explicit transitions rather than silently advancing past a
review boundary:

```text
B1 proposal
  -> awaiting_b1_selection
B1 preserve
  -> ready_for_b2
B2 proposal
  -> awaiting_b2_review
B2 approved/corrected
  -> ready_for_b3
B2 rejected
  -> blocked_rejected
B3 proposal
  -> awaiting_b3_review
B3 approved/corrected
  -> ready_for_assembly
B3 rejected
  -> blocked_rejected
PageIR assembly
  -> assembled
```

Every transition reads one immutable source bundle and publishes one new sibling bundle
through UUID staging plus atomic rename. An existing destination causes `FileExistsError`.
No command infers approval from a successful model response. Parse failures retain their
raw response and can only be corrected or rejected by a named human reviewer.

The CLI commands are:

```text
status
b1-propose
b1-preserve
b2-propose
b2-review
b3-propose
b3-review
assemble
```

The stage-specific imported CLIs remain callable through root `scripts/` wrappers for
compatibility and debugging. The unified CLI delegates to the same public functions; it
does not duplicate B1/B2/B3 logic.

## Artifact Layout

For document `2015p2`, question 18:

```text
output/figure_pipeline/hk-dse-2015-math-p2/q018/
  b1-proposal/
  b1-asset/
  b2-proposal/
  b2-reviewed/
  b3-proposal/
  b3-reviewed/
  assembled/
```

Each stage remains immutable. The unified workflow derives these paths from the stable
document ID and question ID; callers may select a different output root but may not
inject an unsafe relative path.

## PageIR Assembly Contract

Only a B3 bundle whose B2 and B3 statuses are each `approved` or `corrected` is
publishable. `pending`, `failed`, and `rejected` bundles are rejected before any copy.

Assembly is deterministic and makes no model call:

- `source_block_id` is the stable Figure `asset_id`.
- `version_id` is the Figure schema/pipeline version tuple.
- `kind` is `figure`; `integrity` is `ok`.
- Page-space bbox equals the question page bbox offset by the figure bbox in question-crop
  coordinates, after bounds validation.
- Text is a deterministic summary of reviewed classification, subtype, and reviewed
  visible labels; it is not a generated caption.
- The crop filename is derived from `asset_id` and its SHA-256, preventing collisions.
- The source PageIR and reviewed Figure bundle remain unchanged.
- The destination PageIR/crop bundle is published through staging and refuses overwrite.
- The Figure segment is inserted immediately after the one PageIR segment whose
  `source_block_id` identifies the same `pNNN_qNNN` question. Missing or duplicate question
  anchors are errors.

The existing `ocr_pipeline.figure_export` remains available as a legacy preview adapter,
but the DSE reviewed-figure assembler never calls it. Its automatic caption is not an
accepted review decision.

## Error Handling and Auditability

- Validate Pydantic models with `extra="forbid"`; no unknown artifact fields are ignored.
- Verify source question, figure crop, proposal response, and review sidecar hashes before
  copying.
- Preserve source paths as audit references, but all paths used to open files inside a
  bundle must pass safe-relative-path validation.
- Emit machine-readable workflow status and a concise human message.
- Regenerate an import manifest containing target-relative paths, normalized SHA-256,
  source package path, source Figure commit, target commit, and focused test results.
- Never include secrets or environment-variable values in artifacts or reports.

## Test Strategy

Implementation follows RED -> GREEN -> REFACTOR in small batches:

1. Environment smoke and imported Figure suite baseline.
2. Root package/config/wrapper relocation contract.
3. Workflow state detection and transition guards using fake clients only.
4. Unified CLI delegation and stop-at-review behavior.
5. Reviewed Figure -> PageIR deterministic mapping.
6. Atomic, no-overwrite PageIR/crop publication.
7. Regression tests proving OCR locked settings and legacy behavior remain unchanged.
8. Focused Figure suite, affected OCR tests, Ruff, `git diff --check`, and CLI `--help`.

GPU tests and real Qwen/Paddle runs are excluded from this integration batch. They require
a later visible, sequential, timed run after the CPU contract is green.

## Acceptance Criteria

- `figure_pipeline` imports from root `src` and is included in the built wheel.
- All imported Figure tests pass in the rebuilt Python 3.12 environment.
- The unified CLI reports and enforces every human gate.
- Reviewed B2/B3 assets assemble into a new PageIR artifact without mutating inputs.
- Existing destinations and tampered hashes fail before copying.
- Locked OCR settings remain unchanged.
- No GPU OCR is run concurrently or implicitly.
- The target-side integration manifest matches every imported or adapted file.

