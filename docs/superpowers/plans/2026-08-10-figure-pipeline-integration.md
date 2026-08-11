# Figure Pipeline Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Figure B1/B2/B3 into P-ocr as a root-level, review-gated workflow and deterministically assemble approved Figure assets into a new PageIR artifact.

**Architecture:** Keep `ocr_pipeline` and `figure_pipeline` as separate top-level packages sharing Stage1 question IDs, the OCR config, and the local Qwen client. A unified CLI exposes explicit immutable transitions and never advances across B2/B3 human review automatically. A deterministic assembler publishes reviewed Figure segments and crops into a new staged output bundle without mutating OCR or Figure inputs.

**Tech Stack:** Python 3.12, uv, Hatchling, Pydantic v2, Pillow, PyYAML, pytest, Ruff.

## Global Constraints

- DSE MATH Paper 2 keeps the specialized one-question-per-crop regioner.
- Stage2 primary remains PaddleOCR-VL; local Qwen3-VL 4-bit remains fallback/formula OCR.
- Stage3 remains deterministic `sanitize`; no second VLM rewrite.
- `question_id` comes from Stage1; each question remains one PageIR text segment.
- Keep `nup.enabled: false` and `structured_ocr.enabled: false`.
- No external or paid Vision API.
- Runtime paths remain `src/`, `scripts/`, `config/`, `data/`, `output/`, `tests/`, and `run_ocr_pipeline.py`.
- Do not delete or overwrite output, layout, crop, cache, the stale `.venv`, or existing Figure bundles.
- No GPU OCR in this plan. Any later GPU run must be visible, sequential, and timed.
- Use RED -> GREEN -> REFACTOR for every behavior change.
- Do not commit unless the user explicitly asks. End each task with a focused diff and test report instead.
- Sol owns architecture, integration, acceptance, and final output. Luna may only perform the explicitly marked mechanical copy/test/manifest work after the `$double-agents` gates pass.

## File Map

- `src/figure_pipeline/**`: imported immutable B1/B2/B3 models, runners, review logic, and evaluator.
- `src/figure_pipeline/workflow.py`: workflow states, path derivation, and transition guards.
- `src/figure_pipeline/workflow_cli.py`: one CLI surface delegating to stage functions.
- `src/figure_pipeline/pageir.py`: reviewed Figure validation and deterministic `ContentSegment` mapping.
- `src/figure_pipeline/publish.py`: atomic PageIR/crop bundle publication.
- `tests/figure_pipeline/**`: imported contract suite plus workflow/PageIR integration tests.
- `scripts/run_figure_pipeline.py`: unified wrapper.
- `scripts/phase_b*.py`, `scripts/evaluate_b3_sequence_order.py`: relocated compatibility wrappers.
- `config/ocr_pipeline.yaml`: only Figure B2/B3 config additions.
- `pyproject.toml`: include both root packages in Hatch wheel.
- `3.分析結果/docs/figure_pipeline/**`: imported operational docs adapted to target root paths.
- `3.分析結果/reports/figure_integration/import_manifest.json`: regenerated target-side hashes and validation evidence.

---

### Task 0: Rebuild a Non-destructive Python Environment

**Owner:** Sol (environment choice and verification)

**Files:**
- Preserve: `.venv/**`
- Create: `.venv-rebuilt/**` (ignored environment, not source)
- Use: `pyproject.toml`, `uv.lock`, `.python-version`

**Interfaces:**
- Consumes: system `python.exe` version 3.12.10 and the committed lockfile.
- Produces: an executable path stored in `$figureUv` and a project environment selected by `$env:UV_PROJECT_ENVIRONMENT='.venv-rebuilt'`.

- [ ] **Step 1: Record the broken baseline**

Run:

```powershell
python --version
Get-Command uv -ErrorAction SilentlyContinue
& .venv\Scripts\python.exe --version
```

Expected: Python reports `3.12.10`; `uv` is absent; old `.venv` reports `uv trampoline failed to spawn Python child process`.

- [ ] **Step 2: Bootstrap uv into the writable uv data directory**

Run:

```powershell
$uvPrefix = Join-Path $env:APPDATA 'uv\data\codex-bootstrap'
python -m pip install --prefix $uvPrefix uv
$figureUv = Join-Path $uvPrefix 'Scripts\uv.exe'
& $figureUv --version
```

Expected: `uv <version>` and no write to the repository or old `.venv`.

- [ ] **Step 3: Sync a replacement environment from the lockfile**

Run:

```powershell
$env:UV_PROJECT_ENVIRONMENT = '.venv-rebuilt'
& $figureUv sync --locked
```

Expected: `.venv-rebuilt` uses Python 3.12 and the command does not modify `uv.lock`.

- [ ] **Step 4: Run a minimal environment smoke test**

Run:

```powershell
& $figureUv run --locked python -c "import PIL, pydantic, yaml; print('env-ok')"
& $figureUv run --locked python -m pytest --version
git diff -- uv.lock pyproject.toml
```

Expected: `env-ok`, pytest version output, and no diff caused by environment recreation.

---

### Task 1: Relocate and Baseline the Handoff Package

**Owner:** Luna may perform the exact file copy and newline inventory; Sol reviews every path, adapts the one acceptance fixture, and runs acceptance.

**Files:**
- Create: `src/figure_pipeline/**` from handoff `files/2_生產線/src/figure_pipeline/**`
- Create: `tests/figure_pipeline/**` from handoff `files/2_生產線/tests/figure_pipeline/**`
- Modify: `tests/figure_pipeline/test_b2_acceptance.py`

**Interfaces:**
- Consumes: the 24 imported production modules and 19 imported test modules.
- Produces: importable top-level package `figure_pipeline` with unchanged public B1/B2/B3 signatures.

- [ ] **Step 1: Copy only the tests and verify RED**

Mechanically copy the handoff test tree to `tests/figure_pipeline`, preserving fixtures. Run:

```powershell
$env:UV_PROJECT_ENVIRONMENT = '.venv-rebuilt'
& $figureUv run --locked python -m pytest tests/figure_pipeline/test_models.py -q -p no:cacheprovider
```

Expected: collection fails with `ModuleNotFoundError: No module named 'figure_pipeline'`.

- [ ] **Step 2: Copy the runtime package without editing its contracts**

Mechanically copy the handoff runtime tree to `src/figure_pipeline`. Verify the exact public imports:

```python
from figure_pipeline import FigureAsset, FigureProposal, ProposalBundle
from figure_pipeline.classification_runner import classify_bundle
from figure_pipeline.label_ocr_runner import extract_visible_labels_bundle
```

- [ ] **Step 3: Make the external Q18 acceptance fixture explicit**

Add this module-level marker so excluded historical output is not silently treated as an empty fixture:

```python
import pytest

SOURCE = Path("output/figure_pipeline/2015p2/q018")

pytestmark = pytest.mark.skipif(
    not (SOURCE / "figure_asset.json").is_file(),
    reason="requires the separately reviewed Q18 B1 bundle",
)
```

Keep the test body unchanged. This is a conditional external-artifact acceptance test, not a replacement for unit coverage.

- [ ] **Step 4: Run the full imported CPU suite for GREEN**

Run:

```powershell
& $figureUv run --locked python -m pytest tests/figure_pipeline -q -p no:cacheprovider
```

Expected: all self-contained tests pass; exactly one Q18 test may skip when its reviewed bundle is absent.

- [ ] **Step 5: Review the mechanical relocation**

Run:

```powershell
rg -n "2_生產線|1_收集資料|3\.分析結果" src/figure_pipeline tests/figure_pipeline
git diff --check -- src/figure_pipeline tests/figure_pipeline
```

Expected: no production runtime-root literals; test provenance literals are documented exceptions; no whitespace errors.

---

### Task 2: Merge Packaging, Config, and Compatibility Wrappers

**Owner:** Sol

**Files:**
- Create: `tests/figure_pipeline/test_target_integration.py`
- Modify: `pyproject.toml`
- Modify: `config/ocr_pipeline.yaml`
- Create: `scripts/phase_b1_figure_asset.py`
- Create: `scripts/phase_b2_figure_classify.py`
- Create: `scripts/phase_b3_visible_labels.py`
- Create: `scripts/evaluate_b3_sequence_order.py`

**Interfaces:**
- Consumes: `figure_pipeline` package and existing `ocr_pipeline.factory`.
- Produces: wheel inclusion, shared B2/B3 config, and root script entrypoints.

- [ ] **Step 1: Write failing target-layout tests**

Create tests that parse the target files rather than importing build tooling:

```python
from pathlib import Path
import tomllib
import yaml

ROOT = Path(__file__).resolve().parents[2]

def test_wheel_includes_both_runtime_packages() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/ocr_pipeline",
        "src/figure_pipeline",
    ]

def test_figure_config_preserves_locked_ocr_contract() -> None:
    config = yaml.safe_load((ROOT / "config/ocr_pipeline.yaml").read_text(encoding="utf-8"))
    assert config["engines"]["text"] == "paddleocr_vl"
    assert config["pipeline"]["mcq_stage3"] == "sanitize"
    assert config["nup"]["enabled"] is False
    assert config["structured_ocr"]["enabled"] is False
    assert config["figure_classification"] == {
        "enabled": True,
        "max_new_tokens": 256,
        "prompt_version": "figure-b2-v1",
    }
    assert config["figure_label_ocr"] == {
        "enabled": True,
        "max_new_tokens": 384,
        "prompt_version": "figure-b3-v3",
    }
```

Run both tests. Expected: RED because the second wheel package and Figure config sections are absent.

- [ ] **Step 2: Make the minimal packaging/config changes**

Set:

```toml
packages = ["src/ocr_pipeline", "src/figure_pipeline"]
```

Append only the two YAML sections specified in the design. Do not replace any existing OCR key.

- [ ] **Step 3: Relocate the four exact wrappers**

Each wrapper contains only its existing import and `raise SystemExit(main())`; for example:

```python
from figure_pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run focused GREEN and CLI import smoke**

Run:

```powershell
& $figureUv run --locked python -m pytest tests/figure_pipeline/test_target_integration.py tests/figure_pipeline/test_classification_cli.py tests/figure_pipeline/test_label_ocr_cli.py -q -p no:cacheprovider
& $figureUv run --locked python scripts/phase_b1_figure_asset.py --help
& $figureUv run --locked python scripts/evaluate_b3_sequence_order.py --help
```

Expected: tests pass and both help commands exit 0 without loading a GPU model.

---

### Task 3: Add Workflow State and Transition Guards

**Owner:** Sol; Luna may add additional patterned state cases after the core state model is fixed.

**Files:**
- Create: `src/figure_pipeline/workflow.py`
- Create: `tests/figure_pipeline/test_workflow.py`

**Interfaces:**
- Produces: `WorkflowState`, `WorkflowPaths.for_root(root: Path)`, and `inspect_workflow(root: Path) -> WorkflowStatus`.
- Consumes later: `workflow_cli.main` and PageIR assembly.

- [ ] **Step 1: Write failing empty/gated/completed state tests**

Use this public contract:

```python
def test_empty_workflow_needs_b1_proposal(tmp_path: Path) -> None:
    status = inspect_workflow(tmp_path / "q018")
    assert status.state == "needs_b1_proposal"
    assert status.next_command == "b1-propose"

def test_b2_proposal_stops_for_human_review(tmp_path: Path) -> None:
    paths = make_valid_b2_pending_workflow(tmp_path)
    status = inspect_workflow(paths.root)
    assert status.state == "awaiting_b2_review"
    assert status.next_command == "b2-review"

def test_b3_reviewed_is_ready_for_assembly(tmp_path: Path) -> None:
    paths = make_valid_b3_reviewed_workflow(tmp_path)
    status = inspect_workflow(paths.root)
    assert status.state == "ready_for_assembly"
    assert status.next_command == "assemble"
```

Also test B2/B3 rejection, an impossible stage gap, malformed JSON, and tampered crop SHA. Run the empty test; expected RED because `workflow.py` does not exist.

- [ ] **Step 2: Implement the strict state model**

Define:

```python
WorkflowState = Literal[
    "needs_b1_proposal",
    "awaiting_b1_selection",
    "ready_for_b2",
    "awaiting_b2_review",
    "ready_for_b3",
    "awaiting_b3_review",
    "ready_for_assembly",
    "blocked_rejected",
    "assembled",
]

class WorkflowStatus(StrictModel):
    state: WorkflowState
    next_command: str | None
    reason: str
```

`WorkflowPaths.for_root` returns fixed children `b1-proposal`, `b1-asset`, `b2-proposal`, `b2-reviewed`, `b3-proposal`, `b3-reviewed`, and `assembled`. `inspect_workflow` validates every existing upstream bundle before considering a downstream stage and raises `ValueError` on gaps or hash mismatches.

- [ ] **Step 3: Run state tests for GREEN**

Run:

```powershell
& $figureUv run --locked python -m pytest tests/figure_pipeline/test_workflow.py -q -p no:cacheprovider
```

Expected: all state and tamper cases pass without creating output outside `tmp_path`.

---

### Task 4: Map Reviewed Figure Assets to PageIR Segments

**Owner:** Sol

**Files:**
- Create: `src/figure_pipeline/pageir.py`
- Create: `tests/figure_pipeline/test_pageir.py`

**Interfaces:**
- Consumes: a B3 `LabeledFigureAsset` bundle.
- Produces: `load_publishable_asset(bundle_dir: Path) -> LabeledFigureAsset` and `build_reviewed_figure_segment(bundle_dir: Path, *, crop_relpath: str) -> ContentSegment`.

- [ ] **Step 1: Write failing publishability tests**

Cover these exact cases:

```python
def test_pending_b3_is_not_publishable(tmp_path: Path) -> None:
    bundle = make_pending_b3_bundle(tmp_path)
    with pytest.raises(ValueError, match="human-reviewed"):
        load_publishable_asset(bundle)

@pytest.mark.parametrize("status", ["approved", "corrected"])
def test_reviewed_b2_and_b3_are_publishable(tmp_path: Path, status: str) -> None:
    bundle = make_reviewed_b3_bundle(tmp_path, status=status)
    assert load_publishable_asset(bundle).label_ocr.status == status
```

Also reject B2 rejected, B3 rejected, missing crop, and SHA mismatch. Expected RED because `pageir.py` is absent.

- [ ] **Step 2: Write failing deterministic mapping test**

For Q18 with question bbox `(100, 200, 500, 600)` and figure bbox `(10, 20, 110, 120)`, assert:

```python
segment = build_reviewed_figure_segment(
    bundle,
    crop_relpath="figures/hk-dse-2015-math-p2-q018-fig01-a1b2c3d4e5f6.png",
)
assert segment.kind is SegmentKind.FIGURE
assert segment.source_block_id == "hk-dse-2015-math-p2-q018-fig01"
assert segment.bbox.as_int_tuple() == (110, 220, 210, 320)
assert segment.text == "geometry/triangle; labels: A, B"
assert segment.version_id == "figure-b1-v1+figure-b2-v1+figure-b3-v3"
```

- [ ] **Step 3: Implement minimal deterministic validation/mapping**

Read only `figure_asset.json`, validate with `LabeledFigureAsset`, require B2/B3 status in `{"approved", "corrected"}`, resolve and hash-check the crop, compute the page-space bbox, and format labels in reviewed order. Do not call a VLM or import `ocr_pipeline.figure_export`.

- [ ] **Step 4: Run focused GREEN**

Run:

```powershell
& $figureUv run --locked python -m pytest tests/figure_pipeline/test_pageir.py tests/test_page_ir_models.py -q -p no:cacheprovider
```

Expected: all mapping and existing PageIR model tests pass.

---

### Task 5: Publish an Immutable Reviewed PageIR Bundle

**Owner:** Sol; Luna may add patterned failure tests after the publish algorithm is fixed.

**Files:**
- Create: `src/figure_pipeline/publish.py`
- Create: `tests/figure_pipeline/test_publish.py`

**Interfaces:**
- Consumes: existing PageIR JSON, one or more publishable B3 bundle directories, and a new destination directory.
- Produces: `publish_reviewed_figures(*, pageir_path: Path, bundle_dirs: Sequence[Path], destination: Path) -> Path` returning the new PageIR path.

- [ ] **Step 1: Write the failing happy-path atomic publish test**

Create PageIR with one anchor `source_block_id="p006_q018"`. Assert the result:

- leaves source PageIR and B3 trees byte-identical;
- writes the copied crop under `figures/{asset_id}-{sha256[:12]}.png`;
- inserts exactly one Figure segment immediately after `p006_q018`;
- writes `destination/<original pageir filename>`;
- leaves no `.staging-*` directory.

Expected: RED because `publish.py` is absent.

- [ ] **Step 2: Write failing guard tests**

Test existing destination, missing anchor, duplicate anchor, duplicate asset ID, crop hash mismatch, write failure, and rename failure. Every failure must preserve inputs, not create destination, and remove only its own sibling UUID staging directory.

- [ ] **Step 3: Implement staged publication**

Use this signature and operation order:

```python
def publish_reviewed_figures(
    *,
    pageir_path: Path,
    bundle_dirs: Sequence[Path],
    destination: Path,
) -> Path:
    if destination.exists():
        raise FileExistsError(destination)
    # 1. Validate all assets and hashes.
    # 2. Parse and validate all unique question anchors.
    # 3. Create one sibling UUID stage.
    # 4. Copy crops using hash-derived names.
    # 5. Write the new PageIR JSON with deterministic order.
    # 6. Rename stage to destination atomically.
```

The comments above define mandatory operation order; replace them with working code, not placeholders. Sort multiple figures for one question by `asset_id` before insertion.

- [ ] **Step 4: Run focused GREEN**

Run:

```powershell
& $figureUv run --locked python -m pytest tests/figure_pipeline/test_publish.py tests/figure_pipeline/test_pageir.py -q -p no:cacheprovider
```

Expected: all success, ordering, tamper, no-overwrite, and cleanup tests pass.

---

### Task 6: Add the Unified Workflow CLI

**Owner:** Sol

**Files:**
- Create: `src/figure_pipeline/workflow_cli.py`
- Create: `tests/figure_pipeline/test_workflow_cli.py`
- Create: `scripts/run_figure_pipeline.py`

**Interfaces:**
- Consumes: imported B1/B2/B3 public functions, `inspect_workflow`, and `publish_reviewed_figures`.
- Produces: `build_parser() -> argparse.ArgumentParser` and `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write failing parser/status tests**

Assert the parser exposes exactly `status`, `b1-propose`, `b1-preserve`, `b2-propose`, `b2-review`, `b3-propose`, `b3-review`, and `assemble`. `status --root <path>` must print one JSON object equal to `WorkflowStatus.model_dump(mode="json")` and exit 0.

- [ ] **Step 2: Write failing human-gate delegation tests**

Monkeypatch the existing stage functions and assert:

- `b2-propose` consumes `b1-asset`, publishes `b2-proposal`, then reports `awaiting_b2_review`;
- it never calls B2 review or B3 code;
- `b3-propose` refuses unless B2 is approved/corrected;
- `assemble` refuses unless B3 is approved/corrected;
- destination collisions fail before model-client construction.

- [ ] **Step 3: Implement the minimal delegating CLI**

Use `WorkflowPaths` for every path. Reuse the exact imported review models and CLI choice sets rather than creating alternate status vocabularies. Build and close the shared VLM client only in B2/B3 proposal commands. Always print the post-command `WorkflowStatus` as JSON.

Create the wrapper:

```python
from figure_pipeline.workflow_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run focused GREEN and help smoke**

Run:

```powershell
& $figureUv run --locked python -m pytest tests/figure_pipeline/test_workflow_cli.py tests/figure_pipeline/test_workflow.py -q -p no:cacheprovider
& $figureUv run --locked python scripts/run_figure_pipeline.py --help
```

Expected: tests pass; help exits 0; no GPU model is constructed.

---

### Task 7: Preserve the Legacy Boundary and Import Documentation

**Owner:** Sol for boundary tests/docs adaptation; Luna may perform exact documentation copy and hash generation.

**Files:**
- Create: `tests/figure_pipeline/test_legacy_boundary.py`
- Create/modify: `3.分析結果/docs/figure_pipeline/**`
- Create: `3.分析結果/docs/FIGURE_PIPELINE_HANDOFF.md`
- Create: `3.分析結果/reports/figure_integration/import_manifest.json`

**Interfaces:**
- Consumes: imported documentation and final target file set.
- Produces: explicit legacy-vs-reviewed contract and auditable import hashes.

- [ ] **Step 1: Write a failing legacy-boundary test**

Use monkeypatch inspection to assert `figure_pipeline.pageir` and `figure_pipeline.publish` do not import or call `ocr_pipeline.figure_export.export_figures`, and a reviewed Figure publish does not call a VLM. Expected: RED until the modules exist; GREEN after Tasks 4–5 without modifying legacy behavior.

- [ ] **Step 2: Run existing legacy Figure tests unchanged**

Run:

```powershell
& $figureUv run --locked python -m pytest tests/test_figure_export.py tests/test_ingest_figures.py tests/test_publish_figures.py -q -p no:cacheprovider
```

Expected: pass, or report a pre-existing failure caused by user-deleted `homelab` files without repairing unrelated deletions. `tests/test_figure_export.py` must pass before proceeding.

- [ ] **Step 3: Copy and adapt operational documentation**

Replace Figure workspace runtime paths as follows:

```text
2_生產線/src/figure_pipeline -> src/figure_pipeline
2_生產線/tests/figure_pipeline -> tests/figure_pipeline
2_生產線/_script -> scripts
3.分析結果/output/figure_pipeline -> output/figure_pipeline
1_收集資料/data -> data
```

Document that B2/B3 are human gates, Q18 acceptance may require a separately retained bundle, and the target import manifest supersedes the stale source checksum file.

- [ ] **Step 4: Generate and verify the target manifest**

The manifest fields must satisfy this JSON Schema fragment:

```json
{
  "type": "object",
  "required": [
    "schema_version",
    "source_package",
    "source_figure_commit",
    "target_commit_before_integration",
    "files",
    "verification"
  ],
  "properties": {
    "schema_version": {"const": "1.0"},
    "source_package": {"const": "main_figure_integration_2026-08-10/files"},
    "source_figure_commit": {"const": "9396a107"},
    "target_commit_before_integration": {"const": "d8d1171"},
    "files": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "sha256"],
        "properties": {
          "path": {"type": "string", "minLength": 1},
          "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        }
      }
    },
    "verification": {
      "type": "object",
      "required": ["figure_pytest", "ruff", "diff_check"]
    }
  }
}
```

Generate actual SHA-256 values for every imported/adapted Figure source, test, wrapper, and documentation file. Re-read the manifest and assert every listed hash matches the target byte content.

---

### Task 8: Final CPU Verification and Review

**Owner:** Sol; at most one final `double-agents` mechanical verification pass, then Sol independently checks evidence.

**Files:**
- Verify only; update the import manifest verification fields after successful commands.

**Interfaces:**
- Consumes: all prior deliverables.
- Produces: acceptance evidence without a commit or GPU run.

- [ ] **Step 1: Run the complete Figure test suite**

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:UV_PROJECT_ENVIRONMENT = '.venv-rebuilt'
& $figureUv run --locked python -m pytest tests/figure_pipeline -q -p no:cacheprovider
```

Expected: all self-contained tests pass; Q18 may be one documented skip.

- [ ] **Step 2: Run affected OCR regression tests**

```powershell
& $figureUv run --locked python -m pytest tests/test_figure_export.py tests/test_page_ir_models.py tests/test_content_first.py tests/test_content_first_pipeline.py tests/test_dse_mcq_region.py tests/test_mcq_stage3_sanitize.py tests/test_paddleocr_vl_text.py -q -p no:cacheprovider
```

Expected: all selected tests pass with no real GPU model invocation.

- [ ] **Step 3: Run static and CLI verification**

```powershell
& $figureUv run --locked ruff check src/figure_pipeline tests/figure_pipeline scripts/run_figure_pipeline.py scripts/phase_b1_figure_asset.py scripts/phase_b2_figure_classify.py scripts/phase_b3_visible_labels.py scripts/evaluate_b3_sequence_order.py
& $figureUv run --locked python scripts/run_figure_pipeline.py --help
& $figureUv run --locked python scripts/phase_b2_figure_classify.py --help
& $figureUv run --locked python scripts/phase_b3_visible_labels.py --help
& $figureUv run --locked python scripts/evaluate_b3_sequence_order.py --help
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 4: Inspect the focused diff and report unrelated baseline failures separately**

```powershell
git diff --stat
git diff -- pyproject.toml config/ocr_pipeline.yaml src/figure_pipeline tests/figure_pipeline scripts 3.分析結果/docs/figure_pipeline 3.分析結果/reports/figure_integration
git status --short -- .
```

Expected: no deletion or overwrite of user outputs, no secret values, and no changes outside the planned paths. Do not claim the whole repository is green if user-owned deletions make unrelated tests uncollectable.
