# TODOS

## OCR / LaTeX

### CLI `--check-compile` (Ship 1.5 — deferred from Ship 1)

**What:** Add optional `--check-compile` to `run_ocr_pipeline.py` and `arrange_only.py` that runs `latexmk -xelatex` or `xelatex` in the `.tex` output directory, writes a sibling `.log`, and never deletes the draft on failure.

**Why:** Manual compile still works; an opt-in draft gate catches broken delimiters before the teacher edit loop wastes time. Eng review **15B** removed PDF from Ship 1 success — this remains the path to restore compile as Ship 1.5.

**Context:** `/plan-eng-review` (2026-07-21 content-first) decision **D14/15B**: no compile in Ship 1. Still desired as **P1 Ship 1.5**. Prefer shared helper under `src/ocr_pipeline/compile_check.py`; `chdir` to output dir to avoid scattering `.aux` in repo root. See also new item **LaTeX auto-compile PDF (Ship 1.5)**.

**Effort:** M  
**Priority:** P1  
**Depends on:** Ship 1 content-first path green (`.tex`/`.txt`/`.pageir.json`)

### Approach B — LayoutBlock → marking-scheme templates

**Status:** SUPERSEDED (2026-07-21) — do not implement as Ship 1 success path.

**What:** _(Historical)_ Emit stable blocks into fixed LaTeX templates (marking-scheme `tabular` + question stem).

**Why superseded:** Product bar moved to **content-first** (complete formulas + linear TeX). Layout fidelity (解|分|備註 columns) is no longer pass/fail. See design `~/.gstack/projects/pdf-scaner/a1217-main-design-20260721-153800.md` and eng plan `a1217-main-eng-review-plan-20260721-content-first.md`.

**Context:** Replaced by minimal Approach B: PageIR + segmenter + formula_integrity + linear render. Old tabular eng plan `a1217-main-eng-review-plan-20260721.md` is historical only.

**Effort:** —  
**Priority:** —  
**Depends on:** —

### LaTeX auto-compile PDF (Ship 1.5)

**What:** After Ship 1 linear `.tex` is stable, produce `output/<stem>.pdf` via `latexmk -xelatex` (or `xelatex`), wired to optional `--check-compile` / golden helper. Golden may require PDF; interactive keeps `.tex` on compile fail with WARN.

**Why:** Teachers still want a quick PDF preview; eng review deferred it so content integrity is not blocked on TeX toolchain flakiness.

**Context:** Design premise originally listed PDF in Ship 1; eng-review amendment **15B** moves it to Ship 1.5. Pairs with `--check-compile` TODO above.

**Effort:** M  
**Priority:** P1  
**Depends on:** Ship 1 content-first artifacts; `--check-compile` helper

### OCR overlay PDF (Ship 2)

**What:** Render `output/<stem>.ocr_overlay.pdf` — original page image plus OCR text tied to segment `bbox` / `source_block_id`. Replace Ship 1 synthetic page-level ids/bboxes with real LayoutBlock spatial reattach.

**Why:** Proves *where* each OCR string came from; was explicitly staged after content correctness.

**Context:** Design Ship 2; eng decisions overlay=TODO, 6A synthetic ids only in Ship 1. Taste (side panel vs translucent) decided in Ship 2 ticket.

**Effort:** L  
**Priority:** P2  
**Depends on:** Ship 1 PageIR always written; spatial reattach beyond `p{N}_stitched`

### Real MinerU / UniMERNet math path

**What:** Replace MathRouter soft-fail with a real optional MinerU (or UniMERNet) install path for Formula/Equation blocks, keeping VlmClient fallback.

**Why:** Independent formula crops may OCR more accurately than VLM-only when marking schemes are formula-heavy.

**Context:** Architecture review (2026-07-21): do **not** elevate MinerU ahead of content-first IR + integrity. Revisit only if golden edit time is still dominated by wrong formula *bodies*. Prefer MathEngine adapter (MinerU + VlmFallback). _(After content-first Ship 1.)_

**Effort:** L  
**Priority:** P3  
**Depends on:** Ship 1 content-first green; VlmClient seam landed

### VlmClient seam + Qwen2.5-VL-7B 4bit default

**Status:** implemented in code (T7) — smoke-load on GPU still pending golden run

**What:** `VlmClient` protocol + `Qwen25VlClient` default; GLM adapter via `vlm.backend: glm`.

**Files:** `src/ocr_pipeline/vlm_client.py`, `factory.py`, `arrange_only.py`, `config/ocr_pipeline.yaml`

### LayoutArtifact persist (Phase1 resume)

**What:** Write/read `LayoutBlock[]` + page image paths so route/polish can resume without re-running Surya.

**Why:** Makes Surya→route→polish phases real; saves VRAM/time on iteration.

**Context:** Architecture C3. Mirror `arrange_only.py` pattern. _(Useful after content-first; not a Ship 1 gate.)_

**Effort:** M  
**Priority:** P2  
**Depends on:** Content-first path iterable; VlmClient stable enough

## Completed

### Approach B tabular templates (as Ship 1 bar)

**Status:** Completed as superseded decision (2026-07-21 eng-review) — tracked under OCR section as SUPERSEDED with pointer to content-first design. No code delivery required for the old tabular success metric.
