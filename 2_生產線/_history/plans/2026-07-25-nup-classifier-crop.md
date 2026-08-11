# N-up Classifier + Fixed Crop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect 2-up / 4-up exam pages, crop fixed midline or 2×2 panels, run MinerU+Qwen per panel, and emit version-ordered PageIR so dual-version pages no longer L↔R interleave.

**Architecture:** Pre-MinerU gate: lightweight **projection-valley classifier** (CPU, no extra VRAM) → on confident `2_lr` / `4_2x2`, **fixed geometric crop** to `panels/*.png` → existing layout analyze per panel → remap bboxes to page coords + tag `version_id` → stitch/polish/segment in version order. Low confidence or `1` / `uncertain` uses today's whole-page path.

**Tech Stack:** Existing `ocr_pipeline` (Pillow/numpy for projections), pytest, `uv run`, MinerU layout + Qwen trunk unchanged.

**Spec:** `2_生產線/_history/specs/2026-07-25-nup-classifier-crop-design.md`

## Global Constraints

- Product is **P-ocr**; OCR is feedstock only.
- Trunk stays **MinerU layout + Qwen2.5-VL** (greedy); do not load a second layout/VLM for N-up.
- N-up scope MVP: **2-up L/R** and **4-up 2×2** only; no 8-up.
- Crop is **fixed midline / quadrant grid** (optional margin); no XY-Cut++ in this plan.
- Uncertain / low confidence → **whole-page MinerU fallback** (never force-split).
- Version IDs: `v0`…`vN` required; semantic EN/ZH best-effort optional (Task 6).
- `page_index` = physical PDF page; panels do not invent new page indices.
- DONE schema stays **`done_schema: 1`**; no Qdrant contract change required for MVP.
- Commits: only when the user explicitly asks (repo rule); otherwise stop after green tests.
- Tests: `uv run pytest <paths> -q` (repo uses uv + `pythonpath = ["src"]`).

## File map

| Path | Responsibility |
|------|----------------|
| `src/ocr_pipeline/nup_types.py` | `NupClass`, `NupPanel`, `NupDecision` dataclasses |
| `src/ocr_pipeline/nup_crop.py` | Fixed midline / 2×2 pixel crops + write panel PNGs |
| `src/ocr_pipeline/nup_classify.py` | Projection-valley classifier → class + confidence |
| `src/ocr_pipeline/nup_router.py` | Threshold gate; orchestrate classify→crop or fallback; write `nup.json` |
| `src/ocr_pipeline/nup_merge.py` | Remap panel blocks to page coords; order by `version_id` |
| `src/ocr_pipeline/nup_label.py` | Optional semantic label heuristics (EN/ZH) |
| `src/ocr_pipeline/models.py` | `ContentSegment.version_id`; optional `PageResult.version_id` |
| `src/ocr_pipeline/content_first.py` | Serialize `version_id`; preserve through integrity |
| `src/ocr_pipeline/pipeline.py` | Call N-up gate before `_analyze`; merge panels into one `PageResult` |
| `src/ocr_pipeline/factory.py` | Wire `nup:` config |
| `config/ocr_pipeline.yaml` | `nup.enabled`, `confidence_threshold`, `margin_px` |
| `tests/test_nup_crop.py` | Crop geometry |
| `tests/test_nup_classify.py` | Synthetic 1/2/4 pages |
| `tests/test_nup_router.py` | Fallback vs split |
| `tests/test_nup_merge.py` | Version order + bbox remap |
| `tests/test_nup_pageir.py` | `version_id` in pageir JSON |

---

### Task 1: Types + fixed crop

**Files:**
- Create: `src/ocr_pipeline/nup_types.py`
- Create: `src/ocr_pipeline/nup_crop.py`
- Test: `tests/test_nup_crop.py`

**Interfaces:**
- Consumes: Pillow `Image`, `pathlib.Path`
- Produces:
  - `NupClass` enum: `ONE`, `TWO_LR`, `FOUR_2X2`, `UNCERTAIN`
  - `NupPanel(version_id: str, bbox_norm: tuple[float,float,float,float], path: Path | None = None)`
  - `NupDecision(page_index: int, nup_class: NupClass, confidence: float, threshold: float, fallback: bool, panels: list[NupPanel])`
  - `fixed_panel_boxes(nup_class: NupClass, *, margin_norm: float = 0.0) -> list[tuple[str, tuple[float,float,float,float]]]`
  - `crop_panels(image_path: Path, panels: list[NupPanel], out_dir: Path) -> list[NupPanel]` (writes PNGs, fills `path`)

- [x] **Step 1: Write the failing test**

```python
# tests/test_nup_crop.py
from pathlib import Path

from PIL import Image

from ocr_pipeline.nup_crop import crop_panels, fixed_panel_boxes
from ocr_pipeline.nup_types import NupClass, NupPanel


def test_fixed_panel_boxes_two_lr():
    boxes = fixed_panel_boxes(NupClass.TWO_LR)
    assert [v for v, _ in boxes] == ["v0", "v1"]
    assert boxes[0][1] == (0.0, 0.0, 0.5, 1.0)
    assert boxes[1][1] == (0.5, 0.0, 1.0, 1.0)


def test_fixed_panel_boxes_four_2x2():
    boxes = fixed_panel_boxes(NupClass.FOUR_2X2)
    assert [v for v, _ in boxes] == ["v0", "v1", "v2", "v3"]
    # v0 TL, v1 TR, v2 BL, v3 BR
    assert boxes[0][1] == (0.0, 0.0, 0.5, 0.5)
    assert boxes[3][1] == (0.5, 0.5, 1.0, 1.0)


def test_crop_panels_writes_pngs(tmp_path: Path):
    img_path = tmp_path / "page.png"
    Image.new("RGB", (200, 100), (255, 255, 255)).save(img_path)
    panels = [
        NupPanel("v0", (0.0, 0.0, 0.5, 1.0)),
        NupPanel("v1", (0.5, 0.0, 1.0, 1.0)),
    ]
    out = crop_panels(img_path, panels, tmp_path / "panels")
    assert out[0].path is not None and out[0].path.exists()
    assert Image.open(out[0].path).size == (100, 100)
    assert Image.open(out[1].path).size == (100, 100)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_nup_crop.py -q`  
Expected: FAIL (import / not found)

- [ ] **Step 3: Minimal implementation**

```python
# src/ocr_pipeline/nup_types.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class NupClass(str, Enum):
    ONE = "1"
    TWO_LR = "2_lr"
    FOUR_2X2 = "4_2x2"
    UNCERTAIN = "uncertain"


@dataclass
class NupPanel:
    version_id: str
    bbox_norm: tuple[float, float, float, float]  # x1,y1,x2,y2 in [0,1]
    path: Path | None = None
    semantic: str | None = None


@dataclass
class NupDecision:
    page_index: int
    nup_class: NupClass
    confidence: float
    threshold: float
    fallback: bool
    panels: list[NupPanel] = field(default_factory=list)
```

```python
# src/ocr_pipeline/nup_crop.py
from __future__ import annotations
from pathlib import Path

from PIL import Image

from .nup_types import NupClass, NupPanel


def fixed_panel_boxes(
    nup_class: NupClass, *, margin_norm: float = 0.0
) -> list[tuple[str, tuple[float, float, float, float]]]:
    m = max(0.0, min(margin_norm, 0.05))
    if nup_class is NupClass.TWO_LR:
        return [
            ("v0", (0.0 + m, 0.0, 0.5 - m, 1.0)),
            ("v1", (0.5 + m, 0.0, 1.0 - m, 1.0)),
        ]
    if nup_class is NupClass.FOUR_2X2:
        return [
            ("v0", (0.0 + m, 0.0 + m, 0.5 - m, 0.5 - m)),
            ("v1", (0.5 + m, 0.0 + m, 1.0 - m, 0.5 - m)),
            ("v2", (0.0 + m, 0.5 + m, 0.5 - m, 1.0 - m)),
            ("v3", (0.5 + m, 0.5 + m, 1.0 - m, 1.0 - m)),
        ]
    raise ValueError(f"No fixed boxes for {nup_class}")


def _norm_to_px(
    bbox: tuple[float, float, float, float], w: int, h: int
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return (
        max(0, int(x1 * w)),
        max(0, int(y1 * h)),
        min(w, max(1, int(x2 * w))),
        min(h, max(1, int(y2 * h))),
    )


def crop_panels(image_path: Path, panels: list[NupPanel], out_dir: Path) -> list[NupPanel]:
    out_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    result: list[NupPanel] = []
    for p in panels:
        box = _norm_to_px(p.bbox_norm, w, h)
        crop = im.crop(box)
        path = out_dir / f"{p.version_id}.png"
        crop.save(path)
        result.append(NupPanel(p.version_id, p.bbox_norm, path=path, semantic=p.semantic))
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_nup_crop.py -q`  
Expected: PASS

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Projection-valley classifier

**Files:**
- Create: `src/ocr_pipeline/nup_classify.py`
- Test: `tests/test_nup_classify.py`

**Interfaces:**
- Consumes: page image path; `NupClass`
- Produces: `classify_nup(image_path: Path) -> tuple[NupClass, float]`  
  Heuristic (MVP, CPU):
  1. Grayscale → ink mask (pixels darker than threshold).
  2. Vertical projection: look for a **valley near x=W/2** (relative depth vs neighbors) → evidence for `TWO_LR`.
  3. Horizontal projection: valley near y=H/2 + vertical valley → evidence for `FOUR_2X2`.
  4. If both mid-gutters weak → `ONE` with moderate conf, or `UNCERTAIN` if mixed signals.
  5. Confidence ∈ `[0,1]`; document formula in module docstring (e.g. normalized valley depth).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_nup_classify.py
from pathlib import Path

from PIL import Image, ImageDraw

from ocr_pipeline.nup_classify import classify_nup
from ocr_pipeline.nup_types import NupClass


def _two_column_page(path: Path, w=200, h=200) -> None:
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    # Left and right ink blocks with clear center gutter
    d.rectangle([10, 10, 85, 190], fill=(0, 0, 0))
    d.rectangle([115, 10, 190, 190], fill=(0, 0, 0))
    im.save(path)


def _single_column_page(path: Path, w=200, h=200) -> None:
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([40, 10, 160, 190], fill=(0, 0, 0))
    im.save(path)


def test_classify_two_lr(tmp_path: Path):
    p = tmp_path / "two.png"
    _two_column_page(p)
    cls, conf = classify_nup(p)
    assert cls is NupClass.TWO_LR
    assert conf >= 0.75


def test_classify_single_not_two(tmp_path: Path):
    p = tmp_path / "one.png"
    _single_column_page(p)
    cls, conf = classify_nup(p)
    assert cls in (NupClass.ONE, NupClass.UNCERTAIN)
    assert not (cls is NupClass.TWO_LR and conf >= 0.75)
```

Add a similar `_four_quadrant_page` + `test_classify_four_2x2` with TL/TR/BL/BR ink blocks and empty cross gutters.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_nup_classify.py -q`  
Expected: FAIL

- [ ] **Step 3: Minimal implementation**

Implement `classify_nup` in `nup_classify.py` using numpy (already available via project deps) or pure Python sums over grayscale rows/cols. Prefer no new dependencies.

Key helper sketch:

```python
def _projection_valley_score(proj: list[float], mid: int, window: int) -> float:
    """Return 0..1 score: deeper/wider mid valley → higher."""
    # Compare mean ink in mid±window vs mean ink in left/right (or top/bottom) bands.
    ...
```

Decision table:
- `v_score` high, `h_score` low → `TWO_LR`, conf=`v_score`
- `v_score` high and `h_score` high → `FOUR_2X2`, conf=`min(v,h)`
- both low → `ONE`, conf=`1 - max(v,h)`
- ambiguous band → `UNCERTAIN`, conf=`max(v,h)` (still below typical threshold)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_nup_classify.py -q`  
Expected: PASS

- [ ] **Step 5: Commit only if user asked**

---

### Task 3: Router + `nup.json`

**Files:**
- Create: `src/ocr_pipeline/nup_router.py`
- Test: `tests/test_nup_router.py`

**Interfaces:**
- Consumes: `classify_nup`, `fixed_panel_boxes`, `crop_panels`, `NupDecision`
- Produces:
  - `decide_nup(image_path: Path, page_index: int, *, threshold: float, margin_norm: float, page_dir: Path | None, enabled: bool = True) -> NupDecision`
  - `write_nup_json(path: Path, decision: NupDecision) -> None`
  - `read_nup_json(path: Path) -> NupDecision`

Behavior:
- If `enabled=False` → `ONE`, conf=1.0, `fallback=True`, empty panels (caller uses whole page).
- Classify; if class in `{ONE, UNCERTAIN}` OR `confidence < threshold` → `fallback=True`, panels=[].
- Else build boxes via `fixed_panel_boxes`, optionally `crop_panels` when `page_dir` is set (`page_dir / "panels"`).
- Always writable `nup.json` beside the page when `page_dir` provided.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_nup_router.py
from pathlib import Path
from unittest.mock import patch

from ocr_pipeline.nup_router import decide_nup, write_nup_json, read_nup_json
from ocr_pipeline.nup_types import NupClass, NupDecision


def test_low_confidence_falls_back(tmp_path: Path):
    page = tmp_path / "page.png"
    page.write_bytes(b"")  # classify mocked
    with patch("ocr_pipeline.nup_router.classify_nup", return_value=(NupClass.TWO_LR, 0.4)):
        d = decide_nup(page, 0, threshold=0.75, margin_norm=0.0, page_dir=tmp_path)
    assert d.fallback is True
    assert d.panels == []


def test_high_conf_two_splits_and_writes(tmp_path: Path):
    from PIL import Image

    page = tmp_path / "page.png"
    Image.new("RGB", (200, 100), (255, 255, 255)).save(page)
    with patch("ocr_pipeline.nup_router.classify_nup", return_value=(NupClass.TWO_LR, 0.9)):
        d = decide_nup(page, 1, threshold=0.75, margin_norm=0.0, page_dir=tmp_path)
    assert d.fallback is False
    assert len(d.panels) == 2
    assert d.panels[0].path is not None and d.panels[0].path.exists()
    write_nup_json(tmp_path / "nup.json", d)
    loaded = read_nup_json(tmp_path / "nup.json")
    assert loaded.nup_class is NupClass.TWO_LR
    assert loaded.fallback is False
```

- [ ] **Step 2–4:** Implement router + JSON round-trip; run `uv run pytest tests/test_nup_router.py -q` → PASS

- [ ] **Step 5: Commit only if user asked**

---

### Task 4: Merge panel layout blocks

**Files:**
- Create: `src/ocr_pipeline/nup_merge.py`
- Test: `tests/test_nup_merge.py`

**Interfaces:**
- Consumes: `LayoutBlock`, `BBox`, `NupPanel`
- Produces:
  - `remap_block_to_page(block: LayoutBlock, panel: NupPanel, page_w: int, page_h: int) -> LayoutBlock`  
    Panel-local bbox → page bbox:  
    `x_page = panel.x1_px + x_local`, etc. Set `block.meta["version_id"] = panel.version_id`. Reassign `block.image_path` to **page** image (crops stay on panel path in `meta["panel_image"]` if needed).
  - `merge_panel_blocks(panel_blocks: list[tuple[NupPanel, list[LayoutBlock]]], *, page: int, page_image: Path, page_w: int, page_h: int) -> list[LayoutBlock]`  
    Concatenate in `version_id` order (`v0`, `v1`, …); reassign global `order` 0..n-1; unique `block_id` like `p{page:03d}_{version_id}_b{i:03d}`.

- [x] **Step 1: Write the failing test**

```python
# tests/test_nup_merge.py
from pathlib import Path

from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.nup_merge import merge_panel_blocks
from ocr_pipeline.nup_types import NupPanel


def test_merge_orders_versions_and_remaps():
    page_img = Path("page.png")
    v0 = NupPanel("v0", (0.0, 0.0, 0.5, 1.0))
    v1 = NupPanel("v1", (0.5, 0.0, 1.0, 1.0))
    # page 200x100; panel-local block at (10,10)-(30,30) on v1 → page x += 100
    b1 = LayoutBlock(
        block_id="tmp",
        block_type=BlockType.TEXT,
        bbox=BBox(10, 10, 30, 30),
        order=0,
        page=1,
        image_path=Path("v1.png"),
    )
    b0 = LayoutBlock(
        block_id="tmp",
        block_type=BlockType.TEXT,
        bbox=BBox(5, 5, 20, 20),
        order=0,
        page=1,
        image_path=Path("v0.png"),
    )
    merged = merge_panel_blocks(
        [(v0, [b0]), (v1, [b1])],
        page=1,
        page_image=page_img,
        page_w=200,
        page_h=100,
    )
    assert [m.meta["version_id"] for m in merged] == ["v0", "v1"]
    assert merged[1].bbox.x1 == 110.0
    assert merged[0].order == 0 and merged[1].order == 1
```

- [ ] **Step 2–4:** Implement; `uv run pytest tests/test_nup_merge.py -q` → PASS

- [ ] **Step 5: Commit only if user asked**

---

### Task 5: Pipeline + config wire

**Files:**
- Modify: `config/ocr_pipeline.yaml` (add `nup:` block)
- Modify: `src/ocr_pipeline/factory.py` (read nup settings onto pipeline)
- Modify: `src/ocr_pipeline/pipeline.py` (Stage1 loop)
- Test: `tests/test_nup_pipeline_gate.py` (mock layout analyze)

**Interfaces:**
- Consumes: `decide_nup`, `merge_panel_blocks`, existing `_analyze(image_path, page)`
- Produces: For each page image in Stage1:
  1. `decision = decide_nup(..., page_dir=page_subdir_or_page_dir)`
  2. If `decision.fallback` or no panels: `blocks = self._analyze(image_path, page)` as today; optionally tag `meta["version_id"]="v0"`.
  3. Else: for each panel with `path`, `blocks_i = self._analyze(panel.path, page)`; then `blocks = merge_panel_blocks(...)`.
  4. Log: `nup class=… conf=… fallback=… panels=N`
  5. `write_nup_json` under the page artifact area (recommend `page_dir / f"nup_page_{page:03d}.json"` or beside each page PNG as `page_001.nup.json` — pick one and use consistently; prefer `page_dir / "nup" / f"page_{page:03d}.json"`).

Config defaults:

```yaml
nup:
  enabled: true
  confidence_threshold: 0.75
  margin_norm: 0.01
```

Factory: pass `nup_enabled`, `nup_confidence_threshold`, `nup_margin_norm` into `OCRPipeline` (or a small `NupConfig` dataclass held on the pipeline).

- [ ] **Step 1: Write failing test with mocked `_analyze`**

```python
# tests/test_nup_pipeline_gate.py
# Construct a minimal pipeline stub or call a extracted helper:
# analyze_page_with_nup(analyze_fn, image_path, page, nup_cfg, page_dir) -> list[LayoutBlock]

def test_analyze_page_with_nup_splits_when_confident(tmp_path, monkeypatch):
    ...
    # mock decide_nup to return 2 panels; mock analyze_fn called twice with panel paths
    # assert merge used / version_ids present
```

Prefer extracting a pure function `analyze_page_with_nup(...)` in `nup_router.py` or `pipeline.py` so the test does not boot MinerU/VLM.

- [ ] **Step 2–4:** Implement helper + wire pipeline Stage1; run focused tests → PASS

- [ ] **Step 5: Commit only if user asked**

---

### Task 6: PageIR `version_id` + optional semantic labels

**Files:**
- Modify: `src/ocr_pipeline/models.py` — `ContentSegment.version_id: str | None = None`
- Modify: `src/ocr_pipeline/segmenter.py` / `content_first.py` — propagate `version_id` from block.meta when segmenting; JSON field `version_id`
- Create: `src/ocr_pipeline/nup_label.py` — `maybe_label_panels(decision: NupDecision, drafts: dict[str,str]) -> NupDecision`
- Test: `tests/test_nup_pageir.py`
- Test: `tests/test_nup_label.py`

**Interfaces:**
- Segmenter: when building segments from blocks (or after stitch path), copy `block.meta.get("version_id")` onto `ContentSegment.version_id`.
- `write_pageir_json`: include `"version_id": seg.version_id` when not None.
- `apply_integrity_to_page`: preserve `version_id` (and `crop_relpath`) when rebuilding MATH segments.
- Linear render order: already version-ordered if Stage1 merge ordered blocks; if stitch ever reorders, sort segments by `(version_id or "v0", original index)` before render.
- Semantic labeler MVP: if panel draft text has high CJK ratio → `zh`; high ASCII letters → `en`; else leave `vN`. Never rename files mid-run if already written; set `panel.semantic` + optional alias in `nup.json` only.

- [ ] **Step 1: Failing tests for JSON field + label heuristic**

```python
def test_pageir_json_includes_version_id(tmp_path):
    ...
    assert data["pages"][0]["segments"][0]["version_id"] == "v0"


def test_maybe_label_zh_vs_en():
    from ocr_pipeline.nup_label import guess_semantic
    assert guess_semantic("這是中文試題內容") == "zh"
    assert guess_semantic("This is an English stem.") == "en"
```

- [ ] **Step 2–4:** Implement; run `uv run pytest tests/test_nup_pageir.py tests/test_nup_label.py tests/test_content_first.py -q` → PASS

- [ ] **Step 5: Commit only if user asked**

---

### Task 7: Regression + 2014-style fixture check

**Files:**
- Test: `tests/test_nup_interleave_guard.py`
- Optional fixture PNGs under `tests/fixtures/nup/` (synthetic L/R with distinct markers `Q16` / `Q19` painted as text or as separate ink blobs tagged in meta via mock analyze)

**Interfaces:**
- Pure unit (no GPU): mock `analyze_fn` so left panel returns a block whose draft/text is `Q16...` and right returns `Q19...`; after merge+stitch (or merge order assertion), concatenated draft must be `Q16` before `Q19`, never interleaved line-by-line.
- Also assert: when classifier returns `UNCERTAIN`, `analyze_fn` called **once** with full page path.

- [ ] **Step 1: Write failing interleave guard test**

```python
def test_dual_panels_do_not_interleave_question_order():
    # mock panels + merge + assembler.stitch on version-tagged blocks
    ...
    assert draft.index("Q16") < draft.index("Q19")


def test_uncertain_uses_whole_page_once():
    ...
```

- [ ] **Step 2–4:** Fix any merge/pipeline gaps; run:

`uv run pytest tests/test_nup_*.py tests/test_reading_order.py -q`  
Expected: PASS

- [ ] **Step 5: Manual smoke (optional, GPU):** re-OCR one 2014 page with `nup.enabled=true`; confirm `nup/*.json` shows `2_lr` and review bundle no longer zigzags. Record result in `progress.md`.

- [ ] **Step 6: Commit only if user asked**

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Classifier + fixed crop | 1–2 |
| 2-up + 4-up only | 1–2 |
| Uncertain → whole-page fallback | 3, 5, 7 |
| Auto-detect via threshold | 3, 5 |
| `nup.json` artifact | 3 |
| Per-panel MinerU then merge | 4–5 |
| `version_id` + semantic best-effort | 6 |
| No DONE/Qdrant schema bump | (none — intentional) |
| Success: no L↔R interleave | 7 |
| No XY-Cut++ / 8-up | (explicitly omitted) |

## Placeholder / consistency self-review

- Types use `NupClass.TWO_LR` / `FOUR_2X2` consistently across tasks.
- `bbox_norm` is always `(x1,y1,x2,y2)` in `[0,1]`.
- Pipeline helper name: `analyze_page_with_nup` (Task 5); merge API `merge_panel_blocks` (Task 4).
- Commits gated on user request per repo rule (steps note this instead of mandatory git commit).
