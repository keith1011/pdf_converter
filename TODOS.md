# TODOS

## OCR / LaTeX

### CLI `--check-compile` (deferred from Phase 1)

**What:** Add optional `--check-compile` to `run_ocr_pipeline.py` and `arrange_only.py` that runs `latexmk -xelatex` or `xelatex` in the `.tex` output directory, writes a sibling `.log`, and never deletes the draft on failure.

**Why:** Manual compile works, but an opt-in draft gate catches broken delimiters/tables before the teacher edit loop wastes time.

**Context:** `/plan-eng-review` Issue 3 chose document-only for Phase 1 (no CLI flag). Design doc still lists compile gate as desirable. Implement after `sanitize_tex_document` lands and golden page is stable. Prefer shared helper under `src/ocr_pipeline/compile_check.py`; `chdir` to output dir to avoid scattering `.aux` in repo root.

**Effort:** M
**Priority:** P2
**Depends on:** Phase 1 sanitizer + per-page polish fix

### Approach B — LayoutBlock → marking-scheme templates

**What:** Emit stable blocks into fixed LaTeX templates (marking-scheme `tabular` + question stem), with `% TODO: verify` near formula-in-table / low-confidence regions. Extend existing `LayoutBlock`; do not invent a parallel schema.

**Why:** Sanitizer cannot fix wrong column counts or merged cells; teachers need predictable structure for reuse/edit.

**Context:** Approved design (Approach A now / B later). Entry criteria: 3 consecutive checklist pages (marks column, ≥3 formulas, ≥1 table row) with ≤10 min edit + clean compile, OR same page 3× stable under `arrange_only --no-vlm`. Start from `src/ocr_pipeline/models.py` `LayoutBlock` and Stage2 router labels.

**Effort:** L
**Priority:** P2
**Depends on:** Phase 1 entry criteria met

### Real MinerU / UniMERNet math path

**What:** Replace MathRouter soft-fail with a real optional MinerU (or UniMERNet) install path for Formula/Equation blocks, keeping VlmClient fallback.

**Why:** Independent formula crops may OCR more accurately than VLM-only when marking schemes are formula-heavy.

**Context:** Architecture review (2026-07-21): do **not** elevate MinerU ahead of TexSanitize + Qwen default. Stub today is import-only. Revisit only if golden edit time is still dominated by wrong formula *bodies* (not delimiters/tables). Prefer MathEngine adapter with two implementations (MinerU + VlmFallback).

**Effort:** L
**Priority:** P3
**Depends on:** Phase 2.5a golden stable; VlmClient seam landed

### VlmClient seam + Qwen2.5-VL-7B 4bit default

**Status:** implemented in code (T7) — smoke-load on GPU still pending golden run

**What:** `VlmClient` protocol + `Qwen25VlClient` default; GLM adapter via `vlm.backend: glm`.

**Files:** `src/ocr_pipeline/vlm_client.py`, `factory.py`, `arrange_only.py`, `config/ocr_pipeline.yaml`

### LayoutArtifact persist (Phase1 resume)

**What:** Write/read `LayoutBlock[]` + page image paths so route/polish can resume without re-running Surya.

**Why:** Makes Surya→route→polish phases real; saves VRAM/time on iteration.

**Context:** Architecture C3. Eng plan T8. Mirror `arrange_only.py` pattern.

**Effort:** M
**Priority:** P2
**Depends on:** Phase 2.5a sanitize + VlmClient stable enough to iterate

## Completed

_(none yet)_
