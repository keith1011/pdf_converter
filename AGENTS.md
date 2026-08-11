# Repository instructions

P-ocr converts PDFs into editable `.txt`, `.tex`, `.pageir.json`, and
`questions.jsonl`. Chat/UI work is out of scope.

## Read only what the task needs

- Collection, web sources, or PDF preparation: read `1_收集資料/_skill.md`.
- OCR code, layout, engines, or pipeline: read `handoff_ocr.md`, then
  `2_生產線/_skill.md`.
- QA, output review, or reports: read `3.分析結果/_skill.md`.
- Read `task_plan.md`, `findings.md`, and `progress.md` only when task history is
  relevant. `handoff.md` is secondary to `handoff_ocr.md`.

## Locked OCR contract

- DSE MATH Paper 2 uses the specialized one-question-per-crop regioner.
- Stage2 primary is PaddleOCR-VL; local Qwen3-VL 4-bit is fallback/formula OCR.
- Stage3 is deterministic `sanitize`: no second VLM rewrite.
- `question_id` comes from Stage1; each question becomes one PageIR segment.
- Keep `nup.enabled: false` and `structured_ocr.enabled: false`; no external or
  paid Vision API unless explicitly requested.
- Golden set: `data/sources/2015p2.pdf` and `data/pdf_pages/2015p2/layout.json`.

## Work rules

- Use Python 3.12 with `uv`. Make one small change, explain affected files, then
  run focused pytest before continuing.
- Preserve user changes; inspect diffs and never reset or overwrite unrelated work.
- Run GPU OCR visibly, sequentially, with timing; never run two pipelines together.
- Do not delete or overwrite output, layout, crop, or cache without explicit approval.
- Formal ingest requires the quality gate plus Q1--Q45 coverage in layout and
  `questions.jsonl`.
- Never expose secrets, promote unreviewed drafts, or commit unless explicitly asked.
- Runtime paths stay at root: `src/`, `scripts/`, `config/`, `data/`, `output/`,
  `tests/`, and `run_ocr_pipeline.py`.

## Double-agent policy

- `sol-high` owns reasoning, architecture, integration, acceptance, and final output.
- Delegate to `luna_max` only when every global `$double-agents` gate passes.
- Luna may search, summarize, make exact repetitive edits, add patterned tests,
  run validation, and condense logs.
- Luna must not choose the locked MCQ architecture, model selection, quality
  gate, ingest policy, Q1--Q45 coverage behavior, or run concurrent GPU OCR.
- Sol reviews read-only work from compact evidence, mechanical edits with a
  focused diff and tests, and takes full control only on failure, drift, or risk.
- Batch related work. Default to zero auto-reviews; use at most one per
  implementation batch and two only for explicit high-risk triggers.
