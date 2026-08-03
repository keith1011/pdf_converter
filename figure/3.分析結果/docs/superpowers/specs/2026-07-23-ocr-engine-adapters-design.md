# Design: OCR engine adapters + multi-branch comparison

**Date:** 2026-07-23  
**Product:** **P-ocr**（題庫 → AI 老師 Chat）；本設計只動 **OCR 原料管線**，不做 Chat UI。  
**Status:** Approved in brainstorming dialogue (2026-07-23).  
**Repo:** `pdf scaner`

## 1. Goal

Replace the default “everything through Qwen-VL / optional GLM” path with a **pluggable engine** architecture so we can compare three OCR stacks fairly on the same feedstock contract.

**Success criteria (scored):**

1. Teacher edit time on golden drafts (bar remains ≤10 minutes when good).
2. Formula body correctness (integrity / fewer formula edits / `--check-compile` where applicable).

**Recorded but not scored:** wall-clock and per-stage timings (layout / text / formula / finalize). Speed is logged for later; it does **not** enter the ranking weight.

## 2. Decisions locked

| Topic | Choice |
|-------|--------|
| Comparison bar | Edit time + formula quality; speed logged only |
| GOT final output | Formula crops → GOT-OCR 2.0; text crops → PP-OCR (Traditional Chinese); assemble via existing content-first (no full-page GOT pass) |
| Shared surface | Contract + content-first base shared; engines are plugins only |
| Stage3 on experiment branches | Skip VLM polish; route OCR → content-first finalize |
| MinerU line (corrected) | **MinerU layout** + **UniMERNet formulas** + **PP-OCR (Traditional dict) text** |
| GLM | Delete local weights/cache first; keep code until branches stabilize, then remove |
| Approach | Adapter plugins + three thin git branches (not full pipeline forks) |

## 3. Architecture

```
PDF → page images
  → LayoutEngine.analyze(page) → LayoutBlock[]
  → optional LayoutEngine.release()
  → per block:
        TextEngine.ocr(crop)      # text / title / list / table → linear text
        FormulaEngine.ocr(crop)   # formula / equation
  → stitch draft
  → [experiment branches: no Stage3 VLM]
  → content_first.finalize → .tex + .txt + .pageir.json
  → optional --check-compile
  → existing publish / ingest → Qdrant on PC-B
```

### 3.1 Shared (all branches)

- PageIR / `segmenter` / `formula_integrity` / `content_first`
- `compile_check`, CLI report, single-instance GPU lock
- Homelab DONE.json + ingest contract (B is vector/file authority)

**Rule:** no `if backend == ...` inside segmenter / content_first. Branch differences live in adapters + config.

### 3.2 Plugin interfaces (minimal)

| Interface | Responsibility |
|-----------|----------------|
| `LayoutEngine` | `analyze(page_image) → list[LayoutBlock]` (type, bbox, order); optional `release()` |
| `TextEngine` | `ocr(crop) → str` (inline `$...$` allowed) |
| `FormulaEngine` | `ocr(crop) → str` (display math `$$...$$` or one agreed convention) |

Factory wires engines from config.

### 3.3 Branch ↔ engines

| Branch | Layout | Text | Formula | Stage3 VLM |
|--------|--------|------|---------|------------|
| `branch/qwen-vl` | Surya (current) | Qwen2.5-VL crop | Qwen-VL / existing math path | Allowed (snapshot of today’s behavior) |
| `branch/got-ppocr` | DocLayout-YOLO | PP-OCR Traditional Chinese | GOT-OCR 2.0 | Off |
| `branch/mineru-ppocr` | MinerU layout | PP-OCR Traditional dict | UniMERNet | Off |
| `main` | Adapter interfaces + shared contract; not permanently bound to one heavy stack | | | |

Exact branch names may be shortened (`got-ppocr`, `mineru-ppocr`, `qwen-vl`) as long as roles stay clear.

## 4. Git / cleanup rhythm

1. Introduce adapter interfaces on `main` (thin, testable with fakes).
2. Create `branch/qwen-vl` as a snapshot of the current Surya+Qwen path.
3. Create `branch/got-ppocr` and `branch/mineru-ppocr` with their adapters + configs only.
4. **GLM:** delete local Hugging Face / model weights first; leave `glm_client.py` + config marked deprecated until qwen branch no longer needs them; then delete code from `main`.
5. After comparison, merge the winning engines back into `main` adapters; archive losing branches.

## 5. Comparison protocol

- Same PDF: at least `1_收集資料/data/sources/123.pdf` (optional second doc later).
- Outputs must not clobber each other: e.g. `3.分析結果/output/<stem>.<branch_tag>.*` or per-branch subdirs.
- **Scored:** formula edit effort, prose edit time, compile gate result.
- **Logged only:** total wall-clock; layout / text / formula / finalize stage times.
- Do not silently fall back to Qwen on missing GOT/MinerU/PP-OCR deps — fail loud so comparisons stay clean.
- Keep single-instance OCR lock on 12GB VRAM.

## 6. Error handling

- Missing dependency or weights: fail at startup with an explicit message (what to install).
- Single-block OCR failure: empty/WARN for that block; still attempt to write contract artifacts for the job.
- No dual `run_ocr_pipeline` on the same GPU.

## 7. Testing

| Layer | What |
|-------|------|
| Shared unit | Existing segmenter / content_first / compile / lock tests (CPU) |
| Adapter contract | Fake `LayoutEngine` / `TextEngine` / `FormulaEngine` wired into `PipelineManager` |
| GPU smoke | Per branch: `--limit 1`, then full 14p when ready |
| Human D scorecard | Edit time + formula edits + compile; plus timing log |

## 8. Out of scope (this design wave)

- P-ocr Chat / teacher UI
- Second vector DB (Chroma / Cognee / Mengram)
- Full uv migration of the torch stack
- Full-page GOT as final polish (rejected; too slow)
- Using UniMERNet as layout (user correction: MinerU does layout)

## 9. Implementation notes (for writing-plans; not started)

- Prefer extending current `PipelineManager` + `DynamicRouter` to call engines rather than copying `pipeline.py` per branch.
- Reuse `LayoutArtifact` / `--reuse-layout` where layout engines can serialize compatible blocks.
- PP-OCR Traditional Chinese vs Traditional dict may be two configs of the same TextEngine family.
- Document exact package pins (DocLayout-YOLO, GOT-OCR 2.0, MinerU, UniMERNet, PaddleOCR) in the implementation plan when known.

## 10. Approval record

- Approach: adapter plugins + thin branches (option 1).
- Design §1 architecture: OK.
- Design §2 branches / GLM / compare: OK.
- Design §3 data / errors / tests: OK, with speed logged not scored.
