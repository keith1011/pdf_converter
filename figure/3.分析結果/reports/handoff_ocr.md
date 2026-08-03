# Handoff OCR — DSE Paper2 MCQ (for Codex agent)

**Date:** 2026-07-29
**Repo:** `C:\Users\a1217\OneDrive\桌面\aiworkplace\pdf scaner`
**Audience:** Codex / next coding agent — read this first, then `task_plan.md` / `findings.md` / `progress.md`.
**Product:** P-ocr feedstock (OCR → editable TeX). Chat/老師 UI is out of scope here.

Do **not** invent state. Prefer these planning files over chat memory. Never paste secrets (Qdrant keys in MCP / B `.env` only).

---

## 1. Goal (this track)

**DSE MATH CP Paper 2 MCQ** → reliable per-question drafts:

1. Layout: **1 question = 1 box** (stem + figure + A–D)
2. Stage2: VLM OCR per crop → `questions.jsonl`
3. Stage3: **sanitize only** (no VLM rewrite)
4. PageIR: **1 question = 1 segment** → quality gate **pass**
5. Emit: `.txt` / `.tex` / `.questions.jsonl` for teacher edit (≤10 min bar)

Golden doc: **`1_收集資料/data/sources/2015p2.pdf`** · layout artifact: **`1_收集資料/data/pdf_pages/2015p2/layout.json`** (45/45 qids).

---

## 2. Grill locks (do not reopen without user)

| Topic | Locked choice |
|-------|----------------|
| Layout approach | Specialized DSE Paper2 regioner — **not** Docling / generic DocLayout swap |
| Host split | **B** light OCR → `layout.json`; **A** VLM only |
| Figures | Inside the question box (one VLM call per Q) |
| N-up / dual-column | Off (`nup.enabled: false`) |
| Trunk VLM | **Qwen3-VL-8B-Instruct 4bit** (`2_生產線/config/ocr_pipeline.yaml`) |
| Trunk stack | MinerU layout + Qwen text/formula; `transformers>=4.49,<5` |
| MCQ Stage3 | `pipeline.mcq_stage3: sanitize` (Stage2 text + pylatexenc) |
| Formal ingest | Requires quality **pass** |
| Arabic-Qwen3.5-OCR-v4 | **Experiment only** — isolated `.venv-arabic-ocr`; **not** trunk |

---

## 3. Current status (2026-07-28) — GREEN for MCQ emit

| Check | Result |
|-------|--------|
| Layout 2015p2 | 45/45 boxes |
| Full pipeline `--reuse-layout --output-tag mcq` | exit 0 · ~6 min (route≈359s · polish≈0.01s) |
| `questions.jsonl` | **45/45 ABCD**, no 解題 markers |
| Quality | **pass** (`n_segments=45`, `pct_le3=0`, `pct_ge20=1`, `admit=1`) |
| Emit polish | QID not inside `$…$`; A–D on separate lines |
| Teacher-checkable txt | `3.分析結果/output/2015p2.mcq.txt` (also copied to Desktop) |

Artifacts:

```
3.分析結果/output/2015p2.mcq.{txt,tex,questions.jsonl,pageir.json,quality.json,timing.txt,run.log}
```

User said: **題目導出合格了** (export acceptable). Small emit bugs were fixed after that.

### Cross-year repair (2026-07-29)

- User QA is in `error.txt`.
- Regioner fixes: leading orphan A--D recovery, longest increasing qid sequence
  (2020 `II.` misread as `11.`), and sequence-backed incomplete graph questions.
- Orphan bbox follow-up: align `x1` to the same-page detected qid gutter and
  give page-leading orphans 64 px extra top room, with a hard floor below
  `甲部`. User-flagged qids/tall fractions are now inside the overlays.
- Rebuilt 2017, 2018, 2020, 2021, 2022, and 2023 layouts from saved light-OCR
  lines. Read-only replay verifies every 2012--2023 layout has Q1--Q45 with no
  duplicates.
- Pre/post comparison overlays:
  `3.分析結果/output/missing_question_overlays/` and `3.分析結果/output/fixed_question_overlays/`.
- Follow-up visual QA confirmed 2022 Q1/Q5 and 2021 Q40 now include their
  printed qids. The 2022 layout was rebuilt from cached lines in the foreground
  in 4.03 seconds (45/45, 0 incomplete); Q1/Q5 had only been stale artifacts.
- Recovered boxes already align to the same-page left question gutter. Preserve
  the broad right edge because graph/diagram and right-side option content
  would otherwise be at risk of clipping.
- `MCQ_ROUTER_PROMPT` now preserves currency as literal `\$` and tells the VLM
  to copy every formula component exactly.
- No VLM rerun was performed. Existing cross-year txt/jsonl still contain the
  user-reported OCR defects; regenerate and review them before formal ingest.
- Verification: full pytest **248 passed**; Ruff and ty pass on changed code.
- 2013 remains without Stage2 output because its previous OCR run hung.

### Optional Instructor structured Stage2 (2026-07-29)

- Current Qwen3-VL trunk is direct local Transformers `model.generate()` and
  remains 4-bit. Instructor cannot patch this path.
- Added an opt-in OpenAI-compatible Instructor backend in
  `2_生產線/src/ocr_pipeline/mcq_structured.py`, constructed through `vlm_client.py`.
- Pydantic v2 `McqOcrResult` contains stem, exactly A--D choices, visible figure
  labels, uncertain tokens, warnings, and review state. Any uncertain token
  forces `requires_review=true`.
- Stage1 metadata owns `question_id`; the response schema forbids model-supplied
  qids. `render_text(question_id, result)` deterministically restores the
  existing Stage2 plain-text format.
- Default config is disabled + shadow mode. Legacy text continues through
  DraftAssembler/PageIR/TXT/TEX, while `questions.jsonl` gains nullable
  `structured_ocr`.
- Instructor uses `from_provider`, Pydantic `response_model`, and
  `max_retries=1`; constructor rejects retry values above one.
- Stage1 regioner, MinerU general layout, and MCQ Stage3 sanitize are unchanged.
- Verification: focused regression 40 passed; full pytest **262 passed**;
  changed-file Ruff and ty pass.

---

## 4. Architecture (MCQ path)

```
PDF → pages (reuse)
    → layout.json (dse_mcq_region / --reuse-layout)
    → Stage2: crop each TEXT block with meta.question_id
         prompt = MCQ_ROUTER_PROMPT (short, Qwen3 cookbook style)
    → stitch: "N.\n…\nA.\n…" + blank line between questions
    → Stage3 polish_mcq: sanitize (strip junk + pylatexenc keep CJK)
         NOT CONTENT_FIRST VLM polish (that invented solutions)
    → finalize_content_first:
         segment → coalesce_mcq_segments (1 Q = 1 PROSE seg)
         → quality.json + .txt/.tex/.pageir.json
    → questions.jsonl from per-qid chunks (split only before next N.)
```

### Key modules

| File | Role |
|------|------|
| `2_生產線/src/ocr_pipeline/dse_mcq_*.py` | Regioner / profile / layout → `layout.json` |
| `2_生產線/src/ocr_pipeline/routers.py` | `question_id` → `MCQ_ROUTER_PROMPT` |
| `2_生產線/src/ocr_pipeline/prompts.py` | `MCQ_ROUTER_PROMPT`, `MCQ_POLISH_PROMPT` |
| `2_生產線/src/ocr_pipeline/assemble.py` | stitch / `split_question_chunks` / `polish_mcq` sanitize |
| `2_生產線/src/ocr_pipeline/pylatex_assist.py` | Unicode→LaTeX; `unknown_char_policy='keep'` |
| `2_生產線/src/ocr_pipeline/segmenter.py` | `coalesce_mcq_segments`, `normalize_mcq_block_text` |
| `2_生產線/src/ocr_pipeline/quality.py` | Layer A admit + Layer B doc gate |
| `2_生產線/config/ocr_pipeline.yaml` | VLM + `mcq_stage3: sanitize` |
| `2_生產線/config/profiles/math_cp_p2.yaml` | Paper2 profile |

### Critical bugs already fixed (do not regress)

1. **Page polish glued MCQs / invented solutions** → Stage3 sanitize for MCQ.
2. **`split_question_chunks` on any `\n\n`** orphaned A–D in jsonl → split only `\n{2,}(?=\d{1,2}[\.．])`.
3. **Quality fail from atomized PageIR** → merge one question into one segment.
4. **`$4. 0.002=$` / glued options** → peel opener with `(?!\d)`; `normalize_mcq_block_text`.
5. **pylatexenc CJK** → `keep` + `unknown_char_warning=False` (never `ignore`).

---

## 5. How to run

```powershell
cd "C:\Users\a1217\OneDrive\桌面\aiworkplace\pdf scaner"

# Layout only (if rebuilding boxes)
uv run python 2_生產線/_script/dse_mcq_layout_doc.py `
  --pages-dir 1_收集資料/data/pdf_pages/2015p2 --pdf 1_收集資料/data/sources/2015p2.pdf `
  --out-dir 1_收集資料/data/pdf_pages/2015p2 --work-dir 3.分析結果/output/dse_mcq_layout_2015p2 `
  --lines-dir 3.分析結果/output/dse_mcq_layout_2015p2 --no-backup-layout

# Full VLM route + sanitize Stage3 (reuse layout)
uv run python 2_生產線/run_ocr_pipeline.py 1_收集資料/data/sources/2015p2.pdf --reuse-layout --output-tag mcq
```

Offline re-finalize from jsonl (no VLM) if only segmenter/emit changed: see pattern in `progress.md` 2026-07-27/28 notes (group jsonl by page → `finalize_content_first`).

Tests (smoke suite for this track):

```powershell
uv run pytest 2_生產線/tests/test_mcq_segment_merge.py 2_生產線/tests/test_mcq_stage3_sanitize.py `
  2_生產線/tests/test_per_question_emit.py 2_生產線/tests/test_mcq_coalesce.py -q
```

Python: **3.12** · main env: **`.venv`** via `uv` · `PYTHONPATH=src` when needed.

---

## 6. Suggested next work (pick with user)

Priority order unless user redirects:

1. **Teacher QA on `2015p2.mcq.txt`** — spot-check weak OCR (figures, short stems); fix layout/OCR only where evidence shows miss.
2. **Multi-year layout bakeoff** — 2012/13/16 already had regioner work; confirm 45/45 + one VLM pass each if user wants.
3. **Compile check** — `latexmk -xelatex 3.分析結果/output/2015p2.mcq.tex` if teacher wants PDF preview.
4. **Ingest path** — only after quality pass + publish/`DONE.json` discipline (`2_生產線/homelab/DATA_PLANE.md`); do not invent job layouts on `Z:\`.
5. **Do not** promote Arabic-Qwen3.5-OCR-v4 to trunk; do not bump main `transformers` to 5.x (breaks MinerU).

Out of scope unless asked: Paper1, marking schemes, Docling replacement, N-up.

---

## 7. Config cheat-sheet

```yaml
# 2_生產線/config/ocr_pipeline.yaml (relevant)
vlm:
  model_name: Qwen/Qwen3-VL-8B-Instruct
  load_in_4bit: true
  max_new_tokens: 2048
  max_new_tokens_route: 1536
nup:
  enabled: false
pipeline:
  mcq_stage3: sanitize   # or vlm (MCQ_POLISH_PROMPT) — slower, risk of rewrite
```

---

## 8. Planning / routing habits

- Before complex work: read `task_plan.md`.
- After ~2 factual searches: append `findings.md` / `progress.md`.
- Log errors in plan Errors table — no silent retry loops.
- MCP: see `.cursor/rules/mcp-routing.mdc` (gpu, filesystem, context7, qdrant read-only).
- Broader product handoff (A/B/C topology, Qdrant): root `handoff.md` (older; OCR MCQ detail is **this file**).

---

## 9. One-line summary for Codex

**2015p2 MCQ pipeline is green (45/45 ABCD + quality pass); keep Stage3 sanitize + question-block merge; next = teacher QA / multi-year / compile / ingest — not new layout packages or Arabic OCR trunk swap.**
