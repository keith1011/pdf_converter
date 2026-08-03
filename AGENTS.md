# Repository instructions

## Project scope

This repository is the P-ocr feedstock pipeline: PDF -> OCR drafts -> editable
`.txt`, `.tex`, and `.pageir.json`. Chat/UI work is out of scope for this track.

The current handoff is `handoff_ocr.md`. Read it before changing the OCR/MCQ
path, then consult `task_plan.md`, `findings.md`, and `progress.md`. The older
`handoff.md` describes the broader P-ocr/data-plane architecture and is
secondary when it conflicts with `handoff_ocr.md`.

## Current locked MCQ path

- Scope: DSE MATH CP Paper 2 MCQ, one question box containing stem, figure, and
  options A-D.
- Layout: specialized DSE Paper2 regioner; do not replace it with Docling or a
  generic DocLayout swap.
- Host split: light OCR/rules produce `layout.json`; the VLM processes question
  crops only.
- VLM trunk: `Qwen/Qwen3-VL-8B-Instruct`, 4-bit, with `transformers>=4.49,<5`.
- Stage3 for MCQ: `pipeline.mcq_stage3: sanitize`; keep Stage2 text and do not
  use VLM rewriting unless explicitly requested.
- PageIR: coalesce each question into exactly one segment.
- Formal ingest requires the quality gate to pass.
- Keep `nup.enabled: false`.
- Arabic-Qwen3.5-OCR-v4 is an isolated experiment, never the trunk.

Golden validation artifacts are `data/sources/2015p2.pdf`,
`data/pdf_pages/2015p2/layout.json`, and the `output/2015p2.mcq.*` files.

## Development rules

- Use Python 3.12 and the main `.venv` via `uv`; set `PYTHONPATH=src` when
  invoking modules directly.
- Prefer focused tests for the changed path, especially the MCQ segment,
  sanitize, emit, and layout tests.
- Do not run two OCR pipelines concurrently on the 12 GB GPU.
- Preserve existing user changes. Inspect `git status` and diffs before editing;
  do not reset, checkout, or overwrite unrelated work.
- Keep planning files current for substantive work. Record errors in the plan;
  do not silently retry the same failing command.
- Never commit or print Qdrant keys, `.env` contents, MCP secrets, or other
  credentials.
- Do not promote drafts to training data without review.

## Useful commands

```powershell
uv run python scripts/dse_mcq_layout_doc.py `
  --pages-dir data/pdf_pages/2015p2 --pdf data/sources/2015p2.pdf `
  --out-dir data/pdf_pages/2015p2 --work-dir output/dse_mcq_layout_2015p2 `
  --lines-dir output/dse_mcq_layout_2015p2 --no-backup-layout

uv run python run_ocr_pipeline.py data/sources/2015p2.pdf --reuse-layout --output-tag mcq
```

Do not commit changes unless the user explicitly asks.

## Optional Instructor structured Stage2 — 2026-07-29

- The trunk Qwen client is direct local Transformers `model.generate()` in
  4-bit; Instructor cannot patch it and must not replace it.
- `structured_ocr.enabled: false` by default. When explicitly configured with
  an OpenAI-compatible vision endpoint, Instructor runs only for blocks with
  `meta.question_id`.
- Shadow mode defaults to true: legacy Stage2 `text` remains authoritative,
  while validated `McqOcrResult` is added as `structured_ocr` in
  `questions.jsonl`.
- `question_id` always comes from Stage1 block metadata. The structured schema
  forbids a model-supplied qid and requires exactly choices A--D.
- Instructor validation retries are hard-limited to 0 or 1. Never add an
  unbounded retry.
- MCQ Stage3 remains deterministic `sanitize`; no Instructor or structured
  setting may switch it back to VLM rewriting.

## Cross-year status — 2026-07-29

The user reviewed the 2012--2023 text outputs and recorded defects in
`error.txt`. The regioner was repaired from saved RapidOCR lines; no GPU/VLM
OCR was rerun.

- All 2012--2023 layouts now contain exactly Q1--Q45 with no duplicates.
- Fixed: page-leading orphan questions, the 2020 `II.` -> false Q11 jump, and
  2017 Q31 graph choices with sparse option anchors.
- Follow-up fix: recovered orphan crops now reuse the detected question-number
  gutter; page-leading orphans also reserve 64 px above the first light-OCR
  line, clamped below the `甲部` heading. This keeps printed qids and tall
  fraction stems inside the crop.
- `MCQ_ROUTER_PROMPT` now requires literal currency dollar signs as `\$` and
  exact visual transcription of formula parts.
- Pre-fix overlays: `output/missing_question_overlays/`.
- Post-fix overlays: `output/fixed_question_overlays/`.
- 2022 Q1/Q5 were stale pre-gutter artifacts, not a remaining detector defect.
  The 2022 layout was rebuilt on 2026-07-29 (45/45, 0 incomplete), and the
  fixed Q1/Q5 overlays plus the refreshed 2021 Q40 overlay include their
  printed qids.
- Keep the right-side crop extension: it protects diagrams and right-column
  answer choices. Recovered questions already reuse the same-page left gutter;
  do not make right edges content-tight without new clipping evidence.
- 2013 still has no Stage2 MCQ output because its earlier VLM run hung.
- Existing cross-year `.txt` / `.questions.jsonl` are pre-fix artifacts. Do not
  claim the prompt/content defects are corrected until a foreground VLM rerun
  regenerates them and the user reviews the result.

`quality.json` still measures segment structure, not mandatory Q1--Q45 coverage.
Do not treat `verdict: pass` as eligible for formal ingest unless the layout and
newly generated `questions.jsonl` each contain every qid from 1 through 45.

Preserve both overlay sets. Any next OCR batch must run visibly, sequentially,
and with timing recorded; never run two OCR pipelines on the 12 GB GPU.
