# DSE Paper2 MCQ Region (1題1框) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut one layout box per MATH CP Paper 2 MCQ (stem + optional figure + A–D) via light OCR lines + profile rules on B, write `layout.json` compatible with `--reuse-layout` on A, bypassing MinerU shreds on this path.

**Architecture:** Pure rule engine on ordered OCR lines (synthetic in unit tests) → tag stem openers / A–D anchors with left-bias → pair regions → union bbox + crop PNGs → `save_layout_artifact` with `source=dse_mcq_region:math_cp_p2`. Optional OCR adapter later; script accepts precomputed lines JSON or calls OCR if available. Empty/crash → caller falls back to MinerU (WARN).

**Tech Stack:** Existing `ocr_pipeline` (`LayoutBlock`, `layout_artifact`, Pillow), PyYAML profiles, pytest, `uv run`. No hard PP-OCR dependency in unit tests.

**Spec:** `docs/superpowers/specs/2026-07-26-dse-paper2-mcq-region-design.md`

## Global Constraints

- Ideal: **1 MCQ = 1 box** (stem + figure + A–D).
- v1 profile: **MATH CP P2 only** (`config/profiles/math_cp_p2.yaml`); `dual_column: false`.
- Reuse `layout_artifact` v1; `block_type=text`; meta carries `question_id`, `anchors`, `mcq_incomplete`.
- Unit tests use **synthetic OCR lines** only (no PP-OCR / GPU).
- Optional `LightOcr` protocol + script path for B Ubuntu; do not require paddle in CI.
- Bypass MinerU on this path when regions succeed; empty/crash → MinerU fallback (log WARN).
- Do **not** enable nup; do not change quality gate.
- Commits: only when the user explicitly asks — **this plan does not commit**.
- Tests: `uv run pytest <paths> -q` (repo uses uv + `pythonpath = ["src"]`).

## File map

| Path | Responsibility |
|------|----------------|
| `src/ocr_pipeline/dse_mcq_types.py` | `OcrLine`, `LineTag`, `McqRegion`, `McqAnchors` dataclasses |
| `src/ocr_pipeline/dse_mcq_profile.py` | Load/validate subject profile YAML → `McqProfile` |
| `src/ocr_pipeline/dse_mcq_region.py` | Tag lines + pair openers→A–D spans → list[`McqRegion`] |
| `src/ocr_pipeline/dse_mcq_layout.py` | Regions → crops + `LayoutBlock`s + `save_layout_artifact` |
| `src/ocr_pipeline/dse_mcq_ocr.py` | Optional `LightOcr` protocol + JSON lines loader (no hard paddle dep) |
| `config/profiles/math_cp_p2.yaml` | MATH CP P2 patterns / margins / `min_option_hits` |
| `scripts/dse_mcq_regions.py` | CLI: page PNG + lines JSON (or OCR if available) → `layout.json` |
| `tests/test_dse_mcq_profile.py` | Profile load + defaults |
| `tests/test_dse_mcq_region.py` | Opener/option pairing; reject mid-stem `1.` |
| `tests/test_dse_mcq_layout.py` | Crops + layout.json roundtrip via `load_layout_artifact` |

## YAGNI decisions (locked for this plan)

1. **Pure rules first** on synthetic lines — unit tests never import paddle/PP-OCR.
2. **Thin OCR adapter** (`lines_from_json` + optional protocol) — real PP-OCR wiring is a follow-up on B.
3. **Separate script** `scripts/dse_mcq_regions.py` then A `--reuse-layout` — no `--layout-engine` pipeline flag in v1.
4. **Reuse TEXT router** on A — no `mcq_question` prompt variant in this plan.

---

### Task 1: Types + math_cp_p2 profile loader

**Files:**
- Create: `src/ocr_pipeline/dse_mcq_types.py`
- Create: `src/ocr_pipeline/dse_mcq_profile.py`
- Create: `config/profiles/math_cp_p2.yaml`
- Test: `tests/test_dse_mcq_profile.py`

**Interfaces:**
- Consumes: YAML path / dict
- Produces:
  - `OcrLine(text: str, bbox: tuple[float,float,float,float], page_width: float, page_height: float)`
  - `LineKind` enum / tags: `OTHER`, `STEM_CANDIDATE`, `OPTION_A`…`OPTION_D`
  - `TaggedLine(line: OcrLine, kind: LineKind, question_id: int | None = None)`
  - `McqAnchors(A: bool, B: bool, C: bool, D: bool)` with `hit_count` property
  - `McqRegion(question_id: int, bbox: tuple[float,float,float,float], anchors: McqAnchors, incomplete: bool, line_indices: list[int])`
  - `McqProfile(id, dual_column, stem_opener_patterns, option_letters, option_patterns, left_bias_ratio, min_option_hits, pad_px)`
  - `load_mcq_profile(path: Path) -> McqProfile`
  - `default_math_cp_p2_path() -> Path` (repo `config/profiles/math_cp_p2.yaml`)

- [x] **Step 1: Write the failing test**

```python
# tests/test_dse_mcq_profile.py
from pathlib import Path

from ocr_pipeline.dse_mcq_profile import default_math_cp_p2_path, load_mcq_profile


def test_load_math_cp_p2_profile():
    path = default_math_cp_p2_path()
    assert path.is_file()
    p = load_mcq_profile(path)
    assert p.id == "math_cp_p2"
    assert p.dual_column is False
    assert p.min_option_hits == 3
    assert p.left_bias_ratio == 0.25
    assert len(p.stem_opener_patterns) >= 1
    assert "A" in p.option_letters
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dse_mcq_profile.py -q`
Expected: FAIL (import / not found)

- [x] **Step 3: Minimal implementation**

Write `math_cp_p2.yaml` per spec; implement types + `load_mcq_profile` with `yaml.safe_load` (compile patterns with `re.compile`).

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dse_mcq_profile.py -q`
Expected: PASS

- [x] **Step 5: Commit only if user asked**

---

### Task 2: Region rule engine (tag + pair)

**Files:**
- Create: `src/ocr_pipeline/dse_mcq_region.py`
- Test: `tests/test_dse_mcq_region.py`

**Interfaces:**
- Consumes: `list[OcrLine]`, `McqProfile`
- Produces:
  - `tag_lines(lines, profile) -> list[TaggedLine]`
  - `detect_mcq_regions(lines, profile) -> list[McqRegion]`
- Rules (v1, single-column):
  1. Stem candidate: opener regex **and** line `x1` within left `left_bias_ratio` of page width.
  2. Option: option regex + left bias → `OPTION_A`…`D`.
  3. Mid-line / indented `1.` without left bias → NOT stem.
  4. Walk top→bottom: on new stem `question_id`, start region; close at next stem **or** after enough A–D (prefer after D seen); else extend to page bottom / next opener and set `incomplete=True` if `hit_count < min_option_hits`.
  5. BBox = union of member line bboxes (+ `pad_px`).

- [x] **Step 1: Write the failing tests**

```python
# tests/test_dse_mcq_region.py
from ocr_pipeline.dse_mcq_profile import default_math_cp_p2_path, load_mcq_profile
from ocr_pipeline.dse_mcq_region import detect_mcq_regions
from ocr_pipeline.dse_mcq_types import OcrLine

W, H = 1000.0, 2000.0


def _L(text: str, y: float, x1: float = 40.0, x2: float = 800.0, h: float = 30.0) -> OcrLine:
    return OcrLine(text=text, bbox=(x1, y, x2, y + h), page_width=W, page_height=H)


def test_two_questions_with_abcd():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("1. Find the value of x.", 100),
        _L("A. 1", 200),
        _L("B. 2", 240),
        _L("C. 3", 280),
        _L("D. 4", 320),
        _L("2. Which is correct?", 400),
        _L("A. p", 500),
        _L("B. q", 540),
        _L("C. r", 580),
        _L("D. s", 620),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [1, 2]
    assert all(r.anchors.hit_count >= 3 for r in regions)
    assert all(not r.incomplete for r in regions)
    assert regions[0].bbox[3] <= regions[1].bbox[1] + 1  # q1 ends before/at q2


def test_in_stem_decimal_does_not_open():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("1. Compute 1.5 + 2.", 100),
        _L("The answer is 1.5 when x=1.", 140, x1=80.0),  # indented mid "1." must not open
        _L("A. 3", 200),
        _L("B. 4", 240),
        _L("C. 5", 280),
        _L("D. 6", 320),
        _L("2. Next", 400),
        _L("A. a", 500),
        _L("B. b", 540),
        _L("C. c", 580),
        _L("D. d", 620),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [1, 2]


def test_incomplete_when_few_options():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("3. Partial", 100),
        _L("A. only", 200),
        _L("B. two", 240),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert len(regions) == 1
    assert regions[0].incomplete is True
    assert regions[0].anchors.hit_count == 2
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dse_mcq_region.py -q`
Expected: FAIL

- [x] **Step 3: Minimal implementation**

Implement `tag_lines` + `detect_mcq_regions` in `dse_mcq_region.py`.

- [x] **Step 4: Run tests**

Run: `uv run pytest tests/test_dse_mcq_region.py tests/test_dse_mcq_profile.py -q`
Expected: PASS

- [x] **Step 5: Commit only if user asked**

---

### Task 3: Layout writer (crops + layout.json)

**Files:**
- Create: `src/ocr_pipeline/dse_mcq_layout.py`
- Test: `tests/test_dse_mcq_layout.py`

**Interfaces:**
- Consumes: page image `Path`, `list[McqRegion]`, profile id, page number, optional pdf path
- Produces:
  - `regions_to_layout_blocks(image_path, regions, *, page, profile_id, crops_dir, pad_px=0) -> list[LayoutBlock]`
    - Writes `crops/p{page:03d}_q{qid:03d}.png`
    - `block_id` = `p{page:03d}_q{qid:03d}`; `block_type=TEXT`; meta per spec
  - `write_mcq_layout_artifact(..., out_path) -> Path` using `save_layout_artifact`
  - Empty regions → return `None` / empty list (caller treats as MinerU fallback)

- [x] **Step 1: Write the failing test**

```python
# tests/test_dse_mcq_layout.py
from pathlib import Path

from PIL import Image

from ocr_pipeline.dse_mcq_layout import write_mcq_layout_artifact
from ocr_pipeline.dse_mcq_types import McqAnchors, McqRegion
from ocr_pipeline.layout_artifact import load_layout_artifact
from ocr_pipeline.models import BlockType


def test_write_layout_roundtrip(tmp_path: Path):
    page_img = tmp_path / "page_001.png"
    Image.new("RGB", (200, 400), (255, 255, 255)).save(page_img)
    regions = [
        McqRegion(
            question_id=1,
            bbox=(10, 20, 180, 150),
            anchors=McqAnchors(True, True, True, True),
            incomplete=False,
            line_indices=[0, 1, 2, 3, 4],
        ),
        McqRegion(
            question_id=2,
            bbox=(10, 160, 180, 300),
            anchors=McqAnchors(True, True, True, False),
            incomplete=True,
            line_indices=[5, 6, 7],
        ),
    ]
    out = write_mcq_layout_artifact(
        page_img,
        regions,
        page=1,
        profile_id="math_cp_p2",
        out_dir=tmp_path,
        pdf_path=None,
    )
    assert out is not None and out.exists()
    pages = load_layout_artifact(out)
    assert len(pages[0].blocks) == 2
    b0 = pages[0].blocks[0]
    assert b0.block_id == "p001_q001"
    assert b0.block_type == BlockType.TEXT
    assert b0.crop_path is not None and b0.crop_path.exists()
    assert b0.meta["question_id"] == 1
    assert b0.meta["anchors"]["D"] is True
    assert b0.meta["mcq_incomplete"] is False
    assert pages[0].blocks[1].meta["mcq_incomplete"] is True
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dse_mcq_layout.py -q`
Expected: FAIL

- [x] **Step 3: Minimal implementation**

Crop with Pillow; call `save_layout_artifact(..., source=f"dse_mcq_region:{profile_id}")`.

- [x] **Step 4: Run tests**

Run: `uv run pytest tests/test_dse_mcq_layout.py tests/test_dse_mcq_region.py -q`
Expected: PASS

- [x] **Step 5: Commit only if user asked**

---

### Task 4: Lines JSON adapter + CLI script

**Files:**
- Create: `src/ocr_pipeline/dse_mcq_ocr.py`
- Create: `scripts/dse_mcq_regions.py`
- Test: extend `tests/test_dse_mcq_layout.py` or `tests/test_dse_mcq_ocr.py`

**Interfaces:**
- `load_ocr_lines_json(path: Path) -> list[OcrLine]` — schema:
  ```json
  {"page_width": 1000, "page_height": 2000, "lines": [{"text": "...", "bbox": [x1,y1,x2,y2]}]}
  ```
- `try_run_light_ocr(image_path) -> list[OcrLine] | None` — returns `None` if paddle/PP-OCR unavailable (stub OK for v1).
- CLI:
  ```
  uv run python scripts/dse_mcq_regions.py \
    --image path/to/page.png \
    --lines path/to/lines.json \
    --profile config/profiles/math_cp_p2.yaml \
    --out-dir data/pdf_pages/<stem>/
  ```
  Writes `layout.json` + crops; exit non-zero if zero regions (signals MinerU fallback).

- [x] **Step 1: Write failing test for JSON loader**

```python
# tests/test_dse_mcq_ocr.py
import json
from pathlib import Path

from ocr_pipeline.dse_mcq_ocr import load_ocr_lines_json


def test_load_ocr_lines_json(tmp_path: Path):
    p = tmp_path / "lines.json"
    p.write_text(
        json.dumps(
            {
                "page_width": 100,
                "page_height": 200,
                "lines": [{"text": "1. Hi", "bbox": [1, 2, 90, 20]}],
            }
        ),
        encoding="utf-8",
    )
    lines = load_ocr_lines_json(p)
    assert len(lines) == 1
    assert lines[0].text == "1. Hi"
    assert lines[0].page_width == 100
```

- [x] **Step 2–4:** Fail → implement loader + thin CLI → pass focused tests.

- [x] **Step 5: Commit only if user asked**

---

### Task 5: Verify suite + ruff on touched files

- [x] Run: `uv run pytest tests/test_dse_mcq_profile.py tests/test_dse_mcq_region.py tests/test_dse_mcq_layout.py tests/test_dse_mcq_ocr.py -q`
- [x] Run: `uv run ruff check` + `uv run ruff format` on touched `src/ocr_pipeline/dse_mcq_*.py`, `scripts/dse_mcq_regions.py`, tests
- [x] Update `task_plan.md` / `findings.md` / `progress.md`
- [x] Code-review + modern-python + ohm-mcp (per parent agent instructions)

## Out of scope (explicit)

- Full GPU VLM smoke on A
- Enabling nup / quality-gate changes
- Hard PP-OCR install in this repo's Windows CI
- Committing / PR

## Done when

- All Task 1–4 tests green
- `layout.json` from script loads via `load_layout_artifact`
- Plan checkboxes marked; planning files updated
- No commit unless user asks
