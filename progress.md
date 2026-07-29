# Progress Log

## 2026-07-28 14:28 — Wrote handoff_ocr.md for Codex
- Focused DSE Paper2 MCQ OCR handoff: status green, locks, run cmds, next work, anti-regressions.

## 2026-07-28 08:20 — Deploy Arabic-Qwen3.5-OCR-v4 (isolated venv)
- Created `.venv-arabic-ocr` (transformers 5.14 + torch cu126).
- Smoke load+infer OK; Chinese MCQ crop quality poor (Arabic-specialized).
- Trunk unchanged (still Qwen3-VL-8B).

## 2026-07-28 08:15 — Fix QID-in-math + option newlines; refresh txt
- `segmenter`: peel stem opener with `(?!\d)`; `normalize_mcq_block_text` unwrap `$N.$` + split inline A–D.
- Re-finalize `2015p2.mcq` → openers 45/45, ABCD line-start 45/45, quality pass.
- Exported Desktop + opened `output/2015p2.mcq.txt`.

## 2026-07-27 19:34 — Full run + analyze (segment-merge in path)
- Exit **0**; wall **6m02s** (route≈359s · polish≈0.01s).
- **Quality pass** (45 segs, le3=0, ge20=1, admit=1).
- jsonl **ABCD 45/45**, no 解題. Minor: Q4 opener swallowed into `$4. …$` in rendered txt/tex; some options same-line after merge so line-based ABCD on txt < jsonl.

## 2026-07-27 19:27 — Full pipeline re-run + analyze (post segment-merge)
- `uv run python run_ocr_pipeline.py data/sources/2015p2.pdf --reuse-layout --output-tag mcq`

## 2026-07-27 18:30 — MCQ segment merge → quality pass
- Implemented question-block coalesce in `segmenter.coalesce_mcq_segments`.
- Offline re-finalize `2015p2.mcq` from jsonl → **quality verdict=pass** (45 segs, le3=0, ge20=1).
- Tests: `test_mcq_segment_merge` + related green.

## 2026-07-27 16:48 — Stage2 re-route done (short MCQ prompt)
- Exit **0**; wall **5m50s** (route≈347s · polish≈0.01s).
- **jsonl ABCD = 45/45**; no 解題 markers. Quality still fail (segment KPI).
- Chunk-split + short prompt working for emit.

## 2026-07-27 16:42 — Start Stage2 re-route 2015p2 (short MCQ prompt + fixed split)
- `uv run python run_ocr_pipeline.py data/sources/2015p2.pdf --reuse-layout --output-tag mcq`
- Goal: lift ABCD beyond 34/45; verify jsonl keeps options after fixed chunk split.

## 2026-07-27 16:40 — Stage2: fix chunk split + Qwen3-short MCQ prompt
- Confirmed Qwen3 **does** OCR A–D (A/B smoke + `.txt` 34/45); jsonl bug was over-splitting on inner blank lines.
- `split_question_chunks` now lookahead-splits on stem openers only; `MCQ_ROUTER_PROMPT` shortened (cookbook-style).
- Rebuilt `2015p2.mcq.questions.jsonl` → ABCD **34/45** (no VLM re-run).
- Next optional: full Stage2 re-route for remaining ~11 weak options.

## 2026-07-27 16:27 — 2015p2 MCQ re-run done (sanitize Stage3)
- Exit **0**; wall **5m46s** (route≈343s · polish≈0.01s · total≈343s) — Stage3 sanitize OK.
- jsonl **45/45**; txt blank chunks **45**; **no** 解題 markers.
- Still: quality fail; jsonl ABCD-complete only **~2/45** — Stage2 crop OCR dropping options (next lever).
- tex openers missing some qids (17,19,20,29,32,34,45).

## 2026-07-27 16:21 — Start timed 2015p2 MCQ re-run (sanitize Stage3)
- Command: `uv run python run_ocr_pipeline.py data/sources/2015p2.pdf --reuse-layout --output-tag mcq`
- Expect: Stage3 ~instant; wall ≈ Stage2 route (~12m prior); verify no invented solutions + A–D kept.

## 2026-07-27 16:15 — MCQ sanitize Stage3 + prompts (user: 一次改完 + context7)
- Added `MCQ_ROUTER_PROMPT` / `MCQ_POLISH_PROMPT`; TextRouter uses MCQ prompt when `question_id`.
- Stage3 default: `polish_mcq` → sanitize Stage2 text (no VLM); config `mcq_stage3: sanitize|vlm`.
- Blank-before-qid in `render_page_ir`; coalesce no longer glues next stem onto options.
- pylatexenc keep policy confirmed via Context7 `/phfaist/pylatexenc`.
- Tests: `test_mcq_stage3_sanitize` + updated per-question emit — related suite green.
- Next: timed `--reuse-layout --output-tag mcq` re-run to verify fidelity + wall time.

## 2026-07-27 15:35 — Post-run check (user: 跑完了檢查)
- Timing/artifacts OK; 45 jsonl rows; quality fail unchanged.
- Verdict: **結構進步、內容退步** — per-Q boundaries better than page-polish glue era, but Qwen3 polish often solves MCQs / drops options; `.tex` still loses some qids after finalize.
- Logged detail in `findings.md`. GPU idle (~2.3/12.3 GiB).

## 2026-07-27 14:08 — Kill hung polish; fix pylatexenc CJK spam; re-run timed
- Stopped PID shell/python for incomplete 2015p2.mcq run (~15+ min stuck flooding CJK warnings).
- Fix: `UnicodeToLatexEncoder(unknown_char_policy='keep', unknown_char_warning=False)` — keep 漢字, no stderr spam.
- Re-start timed `--reuse-layout --output-tag mcq` → **exit 0**
- **Timing** (`output/2015p2.mcq.timing.txt`): wall **4502s (1h15m02s)**; route=701s · polish=3796s · total=4497s
- Wrote `2015p2.mcq.questions.jsonl` (45 Q); quality still fail; some `near-max tokens` / polish parse fail → draft wrapped

## 2026-07-27 13:48 — Timed VLM re-run 2015p2 (per-question polish + Qwen3)
- Command: `uv run python run_ocr_pipeline.py data/sources/2015p2.pdf --reuse-layout --output-tag mcq`
- Expect longer Stage3 (per-question polish). Timing → `output/2015p2.mcq.timing.txt`

## 2026-07-27 12:42 — Per-question emit + pylatexenc polish assist
- Root cause (prior): page stitch/polish glued MCQs — not layout boxes.
- Fix: MCQ `stitch` → `{qid}.` + blank line between questions; Stage3 `polish` splits and polishes **per question**; write `{source}.questions.jsonl`.
- [pylatexenc](https://github.com/phfaist/pylatexenc): post-VLM `encode_unicode_outside_math` (not a VLM tool). Dep: `pylatexenc>=2.10`.
- Tests: `test_per_question_emit` + polish extract green; pipeline smoke tests set `nup_enabled=False`.

## 2026-07-27 12:30 — Switch trunk VLM to Qwen3-VL-8B-Instruct
- Config: `vlm.model_name: Qwen/Qwen3-VL-8B-Instruct` (4bit kept).
- Loader: prefer `Qwen3VLForConditionalGeneration` when name has `qwen3-vl`; Qwen2.5 path retained.
- Tests: `test_vlm_factory` + greedy **14 passed**.
- Smoke: load ~170s (incl. HF fetch) → class=`Qwen3VLForConditionalGeneration`; text gen `OK`; crop Q2 → `2`. exit 0.
- transformers in main `.venv`: **4.57.6** (already has Qwen3VL).

## 2026-07-27 11:26 — Systematic debug: glued/missing MCQs in 2015p2.mcq
- Layout **not** primary cause: 45 boxes, 45 Stage2 routes; overlays/crops show separate Qs with A–D (e.g. Q2, Q6/Q7, Q35).
- Failure layer: page `stitch` + Stage3 **page** polish → drops 題號、黏題、丟選項；no per-Q jsonl.
- Secondary layout: Q18 orphan crop missing stem (x1=307).
- Next (pending user): per-question emit (題號 + 空行) / skip page polish or polish per Q.

## 2026-07-27 10:45 — Clean output + re-run 2015p2 VLM (timed)
- Deleted old `output/*` document artifacts; kept `dse_mcq_layout_*` + smoke + `.gitkeep`.
- Re-run: `--reuse-layout --output-tag mcq` → **exit 0**
- **Timing** (`output/2015p2.mcq.timing.txt`):
  - Wall: **729.4s** (00:12:09)  START 10:46:18 → END 10:58:27
  - Pipeline: layout=0.001s · **route=300.9s** · **polish=425.4s** · finalize=0.023s · **total=726.3s**
- Artifacts: `output/2015p2.mcq.{tex,txt,pageir.json,quality.json,run.log,timing.txt}`
- Quality still fail (pct_le3=0.38); Stage3 is quiet by design (one line then polish).

## 2026-07-27 10:05 — Fix empty-page polish echoing LATEX_MATH_RULES
- Cause: page 1 (0 MCQ boxes) → empty draft → Stage3 still polished → VLM copied `分數：禁止…` into body.
- Fix: skip VLM on blank draft; reject output that looks like math-rules echo; strip leaked block from `output/2015p2.mcq.{tex,txt}`.
- Tests: `test_polish_extract` 5 passed.

## 2026-07-27 09:40 — Start VLM on 2015p2 MCQ layout
- Command: `uv run python run_ocr_pipeline.py data/sources/2015p2.pdf --reuse-layout --output-tag mcq`
- Layout: `data/pdf_pages/2015p2/layout.json` (15 pages, 45 TEXT blocks, source=`dse_mcq_region:math_cp_p2`)
- GPU preflight: ~2.0/12.3 GiB used before load
- **Done** exit 0 in ~784s (route 311s + polish 466s). Artifacts: `output/2015p2.mcq.{tex,txt,pageir.json,quality.json}`
- Quality gate: **fail** (pct_le3=0.41, pct_ge20=0.13) — expected; KPI was box-first, not ingest pass

## 2026-07-27 09:35 — Q36/Q39 last-on-page bottom pad
- Root cause: last MCQ on page had no next-stem gap → y2 stopped near D + `below_options_pad`.
- Fix: `_snap_vertical_gaps` extends last region to `page_h - footer_margin_px` (160; above footer).
- Verify: Q36/Q39 y2=2179; figure pad-below-ink 184 / 248px. Overlays rebuilt. Tests 15 passed.
- Note: margin=100 swallows footer into crop — keep 160.

## 2026-07-27 09:25 — Fix 2015 figure clip / y-align / overlap
- Preamble: only nearby stem-prose (skip axis crumbs `log3x` / lone `B`).
- Vertical gaps: default → previous Q (keep graphs below options); orphan next → claims gap above A–D.
- Widen x2 to `content_x_max_ratio=0.96`.
- Rebuilt 2015 overlays; 45/45; tests 14 passed. Opened issue pages for re-check.

## 2026-07-27 09:10 — Fix 2012 Q1+Q2 merge; all years 45/45
- Reject glued Latin after stem dot (`2.xs`); token-end check (not pattern `\s*`).
- 2012/13/15/16 layout rebuild → **45/45** each. Overlay: 2012 p2 refreshed.

## 2026-07-27 09:05 — Fix Q8+Q9 merge (option right-bias)
- Options no longer left-biased; rebuilt 4 years from cached lines.
- Pass: 2013/2015/2016 = 45; 2012 = 44 (miss Q1). Overlay refreshed for 2016 p4.

## 2026-07-27 08:55 — Layout bakeoff 2012/13/16
- Ran `dse_mcq_layout_doc.py` on 2012p2, 2013p2, 2016p2 (~2.5 min RapidOCR).
- Results: 2015=45/45 pass; 2012=43 (miss 1,38); 2013=44 (miss 32); 2016=44 (miss 9). All 0 incomplete.

## 2026-07-27 08:50 — Layout rules improved → 2015p2 45/45
- Hardened profile/region: id range, increasing qids, drop incomplete, orphan A–D → next qid.
- Re-ran layout from cached lines → **45 questions, missing=[], incomplete=0**.
- Unit tests 12 passed. Overlays refreshed under `output/dse_mcq_layout_2015p2/`.

## 2026-07-27 08:40 — Full 2015p2 MCQ layout
- Ran `scripts/dse_mcq_layout_doc.py` on all 15 pages (~70s with RapidOCR).
- Wrote `data/pdf_pages/2015p2/layout.json` (48 Q-boxes); overlays in `output/dse_mcq_layout_2015p2/`.
- Gaps: missing Q18; false qids 0/1/2; 4 incomplete regions. Layout-first KPI not yet clean.

## 2026-07-26 23:50 — Smoke 2015p2 p4: 4/4 MCQ boxes
- RapidOCR lines → region cutter → 4 questions (8–11), all A–D complete.
- Profile/rules hardened for real OCR (lone `N.`/`A.`, preamble, D same-row, y-expand to next).
- Overlay: `output/dse_mcq_smoke_2015p2_p4/overlay.png`; `test_dse_mcq_region` 6 passed.
- Next optional: wire light OCR backend; A-side `--reuse-layout`.

## 2026-07-26 23:50 — DSE MCQ region TDD green + review
- Implemented Tasks 1–5; focused `test_dse_mcq_*` green; ruff + ohm review done; no commit.
- Plan: `docs/superpowers/plans/2026-07-26-dse-paper2-mcq-region.md`

## 2026-07-26 23:28 — Design approved: DSE P2 MCQ region
- User confirmed grill locks.
- Wrote `docs/superpowers/specs/2026-07-26-dse-paper2-mcq-region-design.md` (Approved).

## 2026-07-26 23:28 — Grill closed (pending confirm): DSE P2 1題1框
- Locked **C**: v1 KPI = box correctness; quality pass later.
- Full lock table in `task_plan.md` grill section + Next Action shared understanding.
- Await user OK → design spec / writing-plans.

## 2026-07-26 23:27 — Grill: figures = A (併進題框)
- Locked **A**: figure inside same question ROI (1題1框).
- Next: success metric → close grill.

## 2026-07-26 23:26 — Grill: anchor OCR = A (B機→layout.json)
- Locked **A**: B light OCR → question ROI + `layout.json`; A VLM only.
- Next: figures-in-ROI / success metric / close grill.

## 2026-07-26 23:25 — Grill: dual-col = C (單欄 v1 / 開關預設關)
- Locked **C**: single-column first; dual-column profile switch default off.
- Next: line-OCR host / figures / close grill.

## 2026-07-26 23:25 — Grill: subject = C (MATH v1 + profiles)
- Locked **C**: MATH CP P2 gold first; subject profiles for later papers.
- Next: dual-column / line-OCR host.

## 2026-07-26 23:24 — Grill: boundary = B (題號+A–D)
- Locked **B**: open on question number, close/confirm with A–D anchors (math stems often contain `1.`).
- Next: subject scope / column layout / line-OCR host.

## 2026-07-26 23:22 — Grill: Paper2 hook = A (影像→題ROI→VLM)
- Locked pipeline **A**: bypass MinerU shreds; cut question ROIs from page image / light line detect → one box/question → VLM.
- Next grill Q: primary signals for question boundaries.

## 2026-07-26 23:21 — Grill: lock DSE Paper2 題區規則
- Confirmed: ideal **1題1框**; approach = **DSE Paper2 MCQ specialized region detection/rules** (not general layout package swap).
- Updated `task_plan.md` Current Phase + Decisions; `findings.md` grill note.

## 2026-07-25 15:40 — Full nup-full OCR + off-center gutter fix
- Full 8p exit 0 (~843s): `output/2014-DSE-MATH-CP-2.nup-full.*`; GPU peak ~9GB.
- Split in that run: p2/p3/p5/p8 OK; **p4/p6/p7 missed** (true 2-up booklet).
- Root cause: gutter off W/2 (≈0.44–0.57). Fix: search best split in 38–62%; crop uses `split_x`.
- Tests `-k nup` → **27 passed** (incl. real p4/p6/p7). Re-OCR of missed pages not re-run yet.

## 2026-07-25 15:20 — N-up GPU smoke 2014 (limit-3) OK
- Classifier fix: detect **dark spine** + landscape prefers `2_lr` (was missing all dual pages). Threshold 0.70.
- Stage1 (mineru venv first attempt): p1 `1` fallback; p2/p3 `2_lr` panels=2. Then bitsandbytes missing in `.venv-mineru312` → crashed Stage2.
- Resume: `uv run` + `--reuse-layout` → exit 0; total ~318s; GPU peak ~8.3GB / 61% util / ~65°C; released to ~2GB.
- Artifacts: `output/2014-DSE-MATH-CP-2.nup-smoke.*`; `nup/page_00{1,2,3}/nup.json`.
- WARN: polish parse fail; draft wrapped (pre-existing polish fragility).

## 2026-07-25 01:00 — N-up classifier+crop implemented (TDD Tasks 1–7)
- GitHub: repo had **0 open issues**. Created [#2](https://github.com/keith1011/pdf_converter/issues/2) (GPU smoke follow-up). Copilot assign **403 / no MCP assign tool** — assign manually in UI if desired.
- Code: `nup_*` modules + pipeline/factory/`nup:` config; stitch markers; polish per-version chunks; PageIR `version_id`.
- Tests: `uv run pytest tests -k nup -q` → **20 passed**; related suites green; ruff clean on touched files.
- Not committed (await user). Optional next: GPU smoke 2014 (issue #2).

## 2026-07-25 00:53 — N-up design approved + writing-plans
- Brainstorm locked: 2+4 up; uncertain→whole-page; **classifier + fixed midline/2×2** (not XY-Cut++); semantic best-effort; auto-detect.
- Spec: `docs/superpowers/specs/2026-07-25-nup-classifier-crop-design.md`
- Plan: `docs/superpowers/plans/2026-07-25-nup-classifier-crop.md` (Tasks 1–7, TDD)
- Awaiting execution mode (subagent-driven vs inline).

## 2026-07-25 00:37 — Verify 2014 after coalesce re-OCR
- Outputs 00:36. Tests 22 passed (mcq/segmenter/reading_order/prompts).
- Reading order: p1 row_major; p2–8 column_major, 1 flip each — OK.
- MCQ: txt shows `A. -1。` / `C. 0 或 -4。` style lines (was bare `A.` / `-1` / `。`).
- Residual: polish sometimes jams next stem onto same line after `D. …`.

## 2026-07-25 00:30 — MCQ coalesce + prompt harden (VLM/segmenter)
- Investigated fragmentation; web+context7 OCR prompt guidance applied.
- Code: prompts + stitch coalesce + segmenter coalesce; 27 related tests passed.
- User should re-OCR 2014 to see txt/pageir improvement.

## 2026-07-25 00:17 — Verified 2014 re-OCR after column-major
- Outputs mtime 00:14: txt/tex/pageir refreshed; 8p, 19 figures, kinds prose277/math126/figure19.
- Layout on load: p1 row_major; p2–8 column_major with **1** L→R flip each (was 7–23 zigzag).
- txt shows coherent `6.` / `25.` / `30.` then `乙部` / `38.` — no 16↔19 line interleave.
- Residual: within-question option/math fragmentation (VLM/segmenter), not column order.
- Review copy refreshed: `output/_review/2014-DSE-MATH-CP-2/`.

## 2026-07-24 23:45 — Gated two-column reading order
- Implemented `assign_reading_order` / `detect_two_column`; tests 7 passed (+mineru/layout suites).
- 2014 layout on load: p1 row_major; p2–8 column_major (1 flip each).
- Next: re-OCR 2014 with reuse-layout when user asks.

## 2026-07-24 23:22 — Z: batch OK + analysis
- Publish+ingest all 5 → Z: timestamped jobs; **2766/2766** segments.
- Canvas: `canvases/smoke5-ocr-results.canvas.tsx`. Caveat: many figure captions =「細節不清」.

## 2026-07-24 22:51 — Resume 2016 only + Z: batch all 5
- 2012–2015 have txt+pageir; prior job killed after 2015. Resume script skips done docs.

## 2026-07-24 22:28 — Resume after reboot: 2015 + 2016
- Skip 2012/2013/2014 (have txt+pageir). Run remaining then Z: batch `--reindex`.

## 2026-07-24 22:15 — Job died mid-2015 (not clean finish)
- Terminal `90117` last write **12:12**; cut mid `2015p2` Stage2 page2 (`route p002_b016`, no `done`).
- No OCR process / no lock now. Outputs: 2012/2013/2014 complete; **no** 2015/2016 txt+pageir; batch never ran for remaining.
- Likely session/sleep/process kill (no clean `OCR_DONE`/`exit_code`); not the earlier generate-hang pattern (blocks were ~40s).

## 2026-07-24 11:39 — Resume OCR 2014–2016 after VLM fix
- GPU free (~1.8GB); no lock. Starting `full_smoke_5docs_resume.py` (skip 2012/2013).
- Then auto batch publish+ingest `--reindex` to `Z:/`.

## 2026-07-24 11:36 — VLM eos/pad + Stage2 timing (context7)
- Fixed `vlm_client`: stop token ids + greedy GenerationConfig scrub.
- Fixed `routers`: per-block `done … Xs` logs.
- Tests: 10 passed. Ready to resume 2014/2015/2016 when user asks.

## 2026-07-24 11:34 — Killed hung 2014 OCR
- User: kill — first two docs ~10min total; 2014 stuck ~20min on first title generate.
- Killed resume + `run_ocr_pipeline` (2014) PIDs; removed `output/.ocr_pipeline.lock`.
- Done so far: `2012p2`, `2013p2`. `2014` incomplete. Await resume/fix decision.

## 2026-07-24 11:20 — Code check (context7) while OCR runs
- Reviewed `vlm_client.run_vlm_generate` vs transformers v4.57 + Qwen2-VL docs.
- Verdict: chat-template path OK; missing explicit `eos_token_id`/`pad_token_id`; Stage2 silent during long greedy decode; `temperature` warn from model GenerationConfig.
- Logged in `findings.md`. No code change mid-smoke.
- Smoke: `2013p2` done; `2014-DSE-MATH-CP-2` Stage2 active (GPU ~70% util / ~8GB).

## 2026-07-24 09:50 — Start full 5-doc OCR + Z: batch
- PDFs: `2012p2`, `2013p2`, `2014-DSE-MATH-CP-2`, `2015p2`, `2016p2` in `data/sources/`.
- User asked full OCR then batch publish/ingest; `Z:\jobs` OK; GPU ~10GB free.
- Runner: `.superpowers/sdd/full_smoke_5docs.py` (log: `full_smoke_5docs.log`).

## 2026-07-24 09:46 — Prep for 5-doc FIGURE smoke
- User will drop ~5 × ~20pp PDFs with figures into `data/sources/`.
- Expanded MinerU label map: `chart` / `diagram` (+ caption variants → OTHER) → FIGURE.
- Smoke order when files arrive: limit-1 figure check → full OCR → batch ingest.

## 2026-07-24 09:24 — GPU smoke (figure + batch)
- OCR limit-1: `123` ~94s, `789` ~42s (MinerU+Qwen); no MinerU FIGURE labels on these pages.
- Forced figure path: `export_figures` → PNG + caption (`output/_smoke_fig/figures/p001_bFIG.png`, 9KB).
- Batch: temp share (Z: missing) publish+ingest `123` 59/59 + `789` 4/4; Qdrant samples `chunk_version=pageir_v2`.

## 2026-07-24 — Task 7: Planning docs + full regression
- Figure+batch plan Tasks 1–6 code complete (uncommitted); Task 7 docs + suite.
- `uv run pytest -q` → **144 passed**, 1 third-party deprecation warning (surya/Pydantic).
- Updated `task_plan.md` Next Action (plan complete; ColPali still backlog); `findings.md` contract notes (`skip_figures` / `extract_figures` / `pageir_v2` / batch CLI).
- Skipped `handoff.md` (no existing batch command snippet).
- GPU OCR smoke **not** run; no git commit.

## 2026-07-24 — Task 6 fix: SystemExit per-doc continue
- Per-doc `except (Exception, SystemExit)`; preflight rejects `--ingest` without `--publish`.
- New test `test_batch_continues_after_ingest_systemexit`.
- Verification: `uv run pytest tests/test_batch_export.py -q` → **2 passed**.
- Notes appended to `.superpowers/sdd/task-6-report.md`; no commit.

## 2026-07-24 — Task 6: batch_export CLI
- TDD RED: `ModuleNotFoundError: ocr_pipeline.batch_export`.
- Implemented `src/ocr_pipeline/batch_export.py`: stage→publish→ingest, preflight, fail-continue, lazy monkeypatchable homelab imports.
- Verification: focused related suite **15 passed** (`test_batch_export` + job_stage + ingest_figures + figure_export + content_first).
- Report: `.superpowers/sdd/task-6-report.md`; no commit.

## 2026-07-24 — Task 4: staging and figure publication
- TDD RED confirmed: test collection fails because `ocr_pipeline.job_stage` does not exist.
- Added regression coverage for staging figures, publishing nested figure artifacts, accepting listed figures, and rejecting unlisted on-disk figures.
- Implemented clean staging, relative-path publication, and DONE completeness checks for `figures/*.png`.
- Verification: focused 9 passed; full suite 140 passed with 1 third-party deprecation warning; scoped ruff clean.
- Report: `.superpowers/sdd/task-4-report.md`; no commit created.

## 2026-07-24 — Task 3: figure crop/export/finalize wiring
- TDD RED: 2 expected failures (skipped FIGURE had no crop; finalize rejected figure merge input).
- Router now retains FIGURE crops while suppressing Stage2 OCR when `skip_figures=true`.
- Pipeline exports captions to `output/<artifact_source>/figures`, groups them by page, and finalizes them into txt/tex/PageIR.
- Factory/config expose `pipeline.extract_figures` with default `true`.
- Verification: focused 2 passed; required related suite 16 passed; integration 2 passed; full suite 135 passed, 1 third-party deprecation warning; ruff clean.
- Report: `.superpowers/sdd/task-3-report.md`

## 2026-07-24 — Task 2: Figure caption prompt + figure_export
- TDD: 2 RED (`figure_export` missing) → implement → 2 GREEN in `test_figure_export.py`.
- Added `FIGURE_CAPTION_PROMPT`, `export_figures()`; pipeline wiring deferred Task 3.
- Report: `.superpowers/sdd/task-2-report.md`

## 2026-07-24 — Task 1: PageIR figure model + render + JSON
- TDD: 3 RED (missing FIGURE/crop_relpath) → implement → 11 GREEN in `test_page_ir_models` + `test_content_first`.
- Report: `.superpowers/sdd/task-1-report.md`

## 2026-07-24 08:38 — writing-plans: figure caption + batch ingest
- Spec locked: `docs/superpowers/specs/2026-07-24-trunk-qwen-ingest-contract-design.md`
- Plan written: `docs/superpowers/plans/2026-07-24-figure-caption-batch-ingest.md` (Tasks 1–7)
- Awaiting execution choice: subagent-driven vs inline

## 2026-07-24 08:36 — Process: brainstorming before writing-plans
- User rule: open writing plans via Superpowers `/brainstorming` first.
- Added `.cursor/rules/superpowers-brainstorm-first.mdc`; noted in `CLAUDE.md`.

## 2026-07-24 08:21 — Close trunk gaps (uv mineru / skip_figures / MathRouter)
- Wired `skip_figures` into `DynamicRouter` + factory; FIGURE OCR when false.
- Simplified `MathRouter` (no MinerU probe); updated review tests.
- `uv add "transformers>=4.49,<5"` + `--group mineru "mineru[pipeline]"`; default-groups include mineru.
- `uv run pytest`: 127 passed; `import mineru` works in main `.venv`.

## 2026-07-24 08:16 — modern-python check: MinerU + Qwen + Qwen
- Reviewed factory / mineru_layout / vlm_text / vlm_formula / vlm_client / routers / pipeline.
- Verified config load wires trunk correctly; ruff OK; focused pytest 13 passed.
- Fixes: factory default `layout=mineru`; MinerU figure labels → `FIGURE`; trunk factory tests; install error message points at `.venv-mineru312`.

## 2026-07-24 08:09 — Trunk stack: MinerU + Qwen + Qwen
- User locked default OCR: layout=mineru, text=vlm (Qwen), formula=vlm (Qwen).
- Updated `config/ocr_pipeline.yaml`, `task_plan.md`, `findings.md`, design spec trunk layout note.
- Note: main `.venv` has no `mineru` import yet — full OCR with this default uses `.venv-mineru312`.

## 2026-07-23 23:35 — Homelab Wave 1 committed; Python 3.12 pin
- Commit `db664cf`: homelab Wave 1 scripts/ingest/DATA_PLANE, Cursor rules, handbooks, `.python-version`, `requires-python >=3.12,<3.13`
- Commit `11638c9`: refresh `uv.lock` for 3.12-only markers; `uv sync` updated env
- Confirmed `py -0p` has no 3.14; project `.venv` is 3.12.13

## 2026-07-23 23:26 — Homelab Wave 1 GREEN
- SSH A→B OK (`id_ed25519_homeserver` / `keith@192.168.1.107`)
- `ufw` ENABLED (`UFW_DONE` 2026-07-23T15:23:45Z); docs in `DATA_PLANE.md`
- RP `20260723T152007Z`: jobs tar (2 DONE) + full+collection snapshots; restore-drill PASS
- Keys rotated on B; A MCP reader synced; `reader_neg_test.py` PASS (reader 403 / writer OK)
- Ingest `wave1demo` 8/8 + idempotent re-ingest; collection **835** points (`123`=827, `wave1demo`=8)
- Wave 2 not started

## 2026-07-23 — Python 3.12 as project standard
- `.python-version` → 3.12; `requires-python = ">=3.12,<3.13"`.
- Verified: py 3.12.13, torch 2.13.0+cu126 cuda=True, surya import OK, `uv run pytest` **120 passed**.

## 2026-07-23 — modern-python uv migrate + pytest
- Migrated install path to `uv sync` / `uv run`; committed adapter smoke fixes with lockfile.
- `uv run pytest`: 120 passed. Ruff engines clean. MinerU stays in `.venv-mineru312`.

## 2026-07-23 — modern-python: check code (engines)
- Ran ruff check/format on `src/ocr_pipeline/engines` + related tests; fixed I001 import order; formatted 6 files.
- Focused pytest engines: **9 passed**. No full uv migrate (GPU/requirements stacks stay).

## 2026-07-23 23:10 — Wave 1 still blocked on B shell
- Opened interactive SSH window earlier; BatchMode key auth still denied; `WAVE1_B_DONE` absent after two poll windows (~15+10 min).
- Staged for when B is reachable: `wave1-on-b.sh` (ufw + RP + key rotate), then A `wave1-finish-on-a.ps1`.
- A-side already green-ish: scripts, DATA_PLANE draft, RP `20260723T122750Z`, job `wave1demo` published, `qdrant.env.new` staged.
- **Hard gate:** run on B (or password-SSH from A):
  `bash /data/pdf-scaner/backups/ssh-bootstrap/install-pc-a-key.sh`
  `bash /data/pdf-scaner/backups/wave1-scripts/wave1-on-b.sh`

## 2026-07-23 21:10 — Homelab Wave 1 (partial; waiting on B)
- Scripts added under `homelab/scripts/`: ufw, backup RP, restore drill, key apply, reader neg-test, wave1-on-b, A finish helpers.
- Samba sync: `Z:\backups\wave1-scripts\`, `Z:\backups\ssh-bootstrap\pc-a.pub`.
- A→B SSH still blocked (pubkey not on B). Host key for `192.168.1.107` accepted.
- Jobs backup RP `20260723T122750Z` + restore-drill (tar has 1× DONE.json) — A-side; B qdrant snapshot pending SSH/`wave1-on-b.sh`.
- Generated `qdrant.env.new` on Z: for rotation (not echoed).
- Published second doc job `20260723-130314-wave1demo` (not ingested yet).
- **User action on B:** `bash /data/pdf-scaner/backups/ssh-bootstrap/install-pc-a-key.sh` then `bash /data/pdf-scaner/backups/wave1-scripts/wave1-on-b.sh`
- After `WAVE1_B_DONE`: run `homelab/scripts/wave1-finish-on-a.ps1` on A.

## 2026-07-23 — Routing rules acknowledged
- Read and will follow `.cursor/rules/tool-routing.mdc` + `.cursor/rules/planning-with-files.mdc`.
- Working memory stays in `task_plan.md` / `findings.md` / `progress.md`; Skill = workflow, MCP = external evidence; pick both when the domain table says so.

## 2026-07-23 — GPU smoke got-ppocr + mineru-ppocr (limit-1)
- Built `.venv-engines312` (GOT/DocLayout/PP-OCR) and `.venv-mineru312` (MinerU/`transformers` 4.57).
- Adapter fixes: PP-OCR 3.x `predict`, DocLayout `hf_hub_download`, GOT HF-native, MinerU PP-DocLayoutV2/UniMERNet loaders.
- Smokes OK (exit 0): `123.got-ppocr.tex` total=33.880s; `123.mineru-ppocr.tex` total=39.228s. Scorecard timings filled (scores still empty).
- Main `config/ocr_pipeline.yaml` restored to surya/vlm defaults afterward.

## 2026-07-23 — Task 10 P-ocr branch comparison scorecard
- Added `docs/superpowers/evals/p-ocr-branch-scorecard.md` for `qwen-vl`, `got-ppocr`, and `mineru-ppocr`.
- Scored columns are formula edits, prose edit minutes, and compile; `layout_s`, `text_s`, `formula_s`, and `total_s` are logged only, never ranking weight.
- References: spec `docs/superpowers/specs/2026-07-23-ocr-engine-adapters-design.md`; plan `docs/superpowers/plans/2026-07-23-ocr-engine-adapters.md`.

## 2026-07-23 — Task 8 MinerU + UniMERNet experiment
- Added lazy, fail-loud `MineruLayoutEngine` and `UnimernetFormulaEngine`; the formula adapter represents its crop as one full-image display-formula region for MinerU's current UniMERNet API.
- Factory accepts `layout: mineru` and `formula: unimernet`; PP-OCR is reused for text/table routing and the default Surya/VLM configuration is unchanged.
- Added mocked CPU layout, formula, and factory tests plus `requirements-mineru-ppocr.txt`. Focused CPU pytest: **10 passed**; no GPU models were downloaded.
- Main source package committed as `87801bf`; config-only branch `mineru-ppocr` committed as `85a8576`, then workspace returned to `main`.

## 2026-07-23 — Task 7 GOT + DocLayout-YOLO experiment
- Added lazy `DocLayoutYoloEngine` and `GotFormulaEngine`; both convert missing dependencies, unavailable weights, and runtime failures into explicit `EngineError` values with no Qwen fallback.
- Factory accepts `layout: doclayout_yolo` and `formula: got`; branch `got-ppocr` config uses DocLayout-YOLO + PP-OCR + GOT, skips polish, and tags artifacts `got-ppocr`.
- Mocked CPU tests: **7 passed**. GPU smoke skipped because DocLayout-YOLO and PaddleOCR are not installed; report `DONE_WITH_CONCERNS`.

## 2026-07-23 — Task 6 PP-OCR text engine
- Added `PpocrTextEngine` with lazy PaddleOCR import, documented `chinese_cht` default, legacy `.ocr(..., cls=True)` parsing, and explicit missing-dependency `EngineError`.
- Factory now selects PP-OCR for text/table routes under `engines.text: ppocr`; VLM remains the default. Added mocked unit tests and `requirements-ppocr.txt`.
- IDE diagnostics: no errors. Required pytest command and `cmd.exe` fallback both returned no shell exit status, so verification and requested commit remain blocked.
- Report: `.superpowers/sdd/task-6-report.md`.

## 2026-07-23 — Task 4 engine pipeline wiring
- Factory now accepts the `engines` config and wires one `LayoutAnalyzer` both as image source and through `SuryaLayoutEngine`; VLM formula/text/table adapters route via `.ocr()`.
- `PipelineManager` supports optional keyword-only `layout_engine`, `skip_polish`, `output_tag`, and logged `StageTimer` timings, while old combined-layout constructors remain valid.
- Focused Task 4 regression suite: **20 passed** in 1.76s. Report: `.superpowers/sdd/task-4-report.md`.

## 2026-07-23 — writing-plans: OCR engine adapters
- Plan committed: `docs/superpowers/plans/2026-07-23-ocr-engine-adapters.md` (`79dd2f2`)
- Rename commit: `801e9f7` (北辰 → P-ocr)
- Awaiting execution mode: subagent-driven vs inline

## 2026-07-23 — Product rename: 北辰 → P-ocr
- Product display name is now **P-ocr** (same meaning: 題庫 → AI 老師 Chat; OCR = feedstock only)
- Updated `handoff.md`, design spec, `pyproject.toml` description

## 2026-07-23 — handoff.md 依 2026-07-23 P-ocr/Approach B 架構覆寫
- Goal/topology/data ownership/Homelab/Pitfalls 對齊 P-ocr（題庫→AI 老師 Chat；OCR 只是原料）
- 保留 Next actions 與 Key files；無 API key 明文

## 2026-07-23 11:06 — handoff.md written for next agent
- Created repo-root `handoff.md` (goal, status, next actions, architecture, pitfalls, skills/MCP tables, homelab, verify cmds, out-of-scope)
- Verified against `task_plan.md` / `findings.md` / `progress.md` / key OCR modules; MCP catalog all `ready`
- No secrets pasted; points next agent at planning-with-files + commit-or-speed choice

## 2026-07-23 10:16 — tabular/compile fix green
- Option A from /review: strip tabular chrome + linear TABLE_ROUTER + CJK/math delimiter defenses
- Unit tests: 23 passed (`test_segmenter`, `test_content_first*`, `test_formula_integrity`)
- Offline re-finalize `output/123.tex` (backup `.tex.bak_tabular`) → **COMPILE_OK**, PDF ~101KB
- Still pending: commit VRAM/greedy fixes; Phase 2.8 speed; optional full OCR re-run with new table prompt

## 2026-07-23 09:05 — idempotent ingest PASS
- Re-ingest same job → `UPSERTED 827/827`; collection `points 827` (no duplication)
- Wave 1 smoke for doc 123 green
- Job `20260723-005247-123` → **827 points** in `exam_segments_v1`
- Publish + ingest path works end-to-end on Samba + B Qdrant
- Next: idempotent re-ingest smoke; optional 2nd doc; rotate exposed writer key
- Publish OK: `Z:\jobs\20260723-005247-123`
- Ingest fail: fastembed model id must be `nomic-ai/nomic-embed-text-v1.5` (fixed)
- Note: writer key appeared in terminal history — rotate when convenient
- Added `homelab/ingest/` (`done.py`, `publish.py`, `ingest.py`) + `tests/test_done_schema.py` (4 passed)
- Next for user: pip install ingest reqs → publish `123` to Z: → ingest with writer key

## 2026-07-23 08:35 — MCP → B verified
- `~/.cursor/mcp.json`: URL `192.168.1.107:6333`, reader key set, `QDRANT_READ_ONLY=true`
- readyz 200 + collections API ok (empty — fresh B; old localhost memories not migrated)
- Wave 0 acceptance: SSH + Qdrant + Samba + MCP all green

## 2026-07-23 08:17 — Next: Samba + MCP
- Wave 0 Qdrant green overnight; apt upgrade + samba package installed
- Today: configure Samba share → map on A → point Cursor MCP reader at B

## 2026-07-23 01:09 — Wave 0 Qdrant green
- `docker compose up` on B OK; keys saved by user (not in chat/git)
- Acceptance: A/B can hit `http://192.168.1.107:6333/readyz`
- SSH: `keith@100.101.145.120` (Tailscale) / LAN `192.168.1.107`
- Next (tomorrow): Samba `jobs/`; Cursor MCP → B reader key; optional ufw

## 2026-07-23 01:02 — B Ubuntu online
- Host: `homeserver` / user `keith`
- LAN: `192.168.1.107` (`enp5s0`); Tailscale: `100.101.145.120`
- A→B SSH OK (`ssh keith@100.101.145.120`)
- Next: Docker + Qdrant `readyz` on B

## 2026-07-22 23:14 — Ubuntu install blocked
- Symptom: Ubuntu installer crashes at Storage probing (tried unplug NIC, nomodeset, ip=off, minimized)
- Decision: allow **Debian 12 netinst** as official Wave 0 fallback; also try BIOS AHCI + disconnect extra disks
- Updated `homelab/README.md`

## 2026-07-22 21:26 — Homelab Wave 0 start
- OS decision: **Ubuntu Server 24.04 LTS** on PC-B
- Added repo `homelab/`: README checklist, `docker-compose.yml` (Qdrant v1.13.2), `.env.example`, `DATA_PLANE.md`
- Blocked on physical: USB install of Ubuntu on B
- Next: user installs OS → Docker → `readyz` from A via LAN

## 2026-07-22 20:00 — /office-hours dual-PC infra
- Topic: PC-A (9600X+4070S win) OCR GPU workstation vs PC-B (5600X+1660S → Linux) for MCP + storage + always-on services
- Prior designs: `~/.gstack/projects/pdf-scaner/a1217-main-design-20260721-*.md` (OCR content-first APPROVED)
- Phase 3 Qdrant still optional-parallel in `task_plan.md`; user now wants home-lab placement for Qdrant MCP, vector DB, Ollama/vLLM, SearXNG, CI runner, Samba/NFS, Tailscale
- One-time: telemetry=community, proactive=true, CLAUDE.md skill routing added (`02a68a6`)
- Mode: **Builder** (D4=C) — dual-PC home lab design, not startup diagnostic
- Coolest version (D5): **B+C hybrid** — OCR→vector NL检索题库 + always-on homelab (boot green, remote/phone)
- Audience (D6): **A+B** — future self (edit/exam) + teacher friends who also grade/write
- Fastest path (D7): **A** (over rec B) — B = Linux always-on NAS + MCP host first; OCR→vector demo = weekend 2
- Closest existing (D8): **A** + clarify — Qdrant **storage on B**; extract/analyze on A; outputs ingest to Qdrant; A realtime query/view
- 10x / north star (D9=D): OCR=step1 → 题库 → **AI 老師 Chat**；Chat LLM on A；data on B；B light LLM for **agent collab** (not main tutor); scale HW/rent later if success
- Status: Design **APPROVED** 2026-07-22 — `a1217-main-design-20260722-210437.md`
- Next assignment: B Linux + LAN Qdrant `readyz` from A (no Chat/SearXNG/LLM)
- Topology locked: C→RustDesk→A(Cursor)→LAN→B(Qdrant)


## 2026-07-22 16:03–16:46 — full 14-page golden
- Command: `run_ocr_pipeline.py data\sources\123.pdf --check-compile`
- Log: `golden_run_full14_cf.log` (~43 min)
- Monitor OK: layout→`Stopped docker VLM`→Stage2 all 14→Stage3; GPU ~7GB steady; no OOM
- **Result:** TEX/TXT/pageir refreshed 16:46; `EXIT:12` (compile failed); PDF still old 15:40
- Compile errors: tabular/`\hline` inside math mode (`Missing $`, `Misplaced \noalign`)
- Content-first polish did not fully strip Stage2 Markdown/LaTeX tables on later pages

## 2026-07-22 — content-first + compile + VRAM stability

### Landed (committed)
- `dbd2e02` Ship content-first OCR with PageIR and per-page polish
- `365c186` Add optional `--check-compile` gate for Ship 1.5 PDF

### Landed (uncommitted — needs commit)
- Greedy VLM decode (fixes CUDA multinomial assert)
- `layout.release()` docker-stops `surya-vllm-*` (fixes Stage3 OOM)

### Verification
| Run | Result |
|-----|--------|
| Unit: layout release + greedy | 7 passed |
| Surya release GPU check | ~11GB → ~390MB after docker stop |
| `run_ocr_pipeline.py ... --limit 1 --reuse-images --check-compile` | **exit 0** |
| Artifacts | `123.pdf` 26KB, `.tex`/`.txt`/`.pageir.json`/`.log` refreshed ~15:40 |

### Monitor notes
- Avoid two concurrent `run_ocr_pipeline` PIDs on 12GB
- Expect log lines: `Stopped docker VLM: surya-vllm-…` before Stage2

### planning-with-files
- User requested **always on**
- Added `.cursor/rules/planning-with-files.mdc` (`alwaysApply: true`)
- Synced `task_plan.md` / `findings.md` / `progress.md` to current state

## Earlier (2026-07-21 excerpt)
- Full 14p Stage3 OOM → auto polish_per_page; later superseded by content-first always per-page
- limit-2 / full2 golden history in git/logs

## Next
1. User review of OCR adapter design spec; then writing-plans
2. Optional: full 14-page OCR re-run with new TABLE_ROUTER + `--check-compile`
3. Homelab follow-ups (still uncommitted under `homelab/`)

## 2026-07-26 — Quality gate TDD + GitHub hybrid
- Listed open issues (#1 PR draft, #2 N-up smoke); created #4 core + #3 wiring
- Copilot assign failed (`Bot does not have access`); implemented both locally with TDD
- `uv run pytest` quality+ingest gate suites green; ruff --fix on touched tests/batch_export
- ohm: type hints A; complexity flag on `build_quality_report` (defer extract — covered by tests)
- Spec approved + code uncommitted pending user commit ask

## 2026-07-25 — nup-v2 hang → EOS harden → resume
- Died mid Stage2 (~2h, ~45s/block). Timing ≈ full 1024-token burn; stub prompt reproduced `!` wall; real prompts now early-stop.
- Fix: prefer `generation_config.eos_token_id` list; WARN on near-max `n_new`. Tests 9 passed.
- Smoke `--limit 1 --reuse-layout --skip-polish`: after load, blocks ~0.7–4s (not 45s). No WARN.
- Full resume exit 0: `TIMING: route=400s polish=389s total=802s` → `output/2014-DSE-MATH-CP-2.nup-v2.*`

## 2026-07-23 — Brainstorm: multi-engine OCR branches (spec written)
- Locked: D scored (edit time + formulas); speed logged not weighted
- GOT path A; shared contract + adapters; Stage3 off on experiment branches
- MinerU layout + UniMERNet formula + PP-OCR text; GLM weights first, code later
- Spec: `docs/superpowers/specs/2026-07-23-ocr-engine-adapters-design.md`
- No implementation until user approves spec → writing-plans

## 2026-07-23 — modern-python cleanup (ordered)
1. Shared `run_vlm_generate` / `resize_image` / `strip_fences` in `vlm_client.py`; GLM delegates
2. Removed `decide_polish_per_page` + auto-warn dead path; CLI `--polish-per-page` deprecated no-op; lock uses `with` (no atexit)
3. Light tooling: `pyproject.toml` (ruff only) + `requirements-dev.txt`; `uv pip install -p .venv ruff`; `ruff check src/ocr_pipeline …` clean; 26 related tests passed
- Did **not** migrate torch stack to uv / delete requirements-ocr-pipeline.txt

## 2026-07-23 — Phase 2.8 speed implemented
- Config: `vlm.max_new_tokens: 2048`, `max_new_tokens_route: 1024`; factory wires route budgets into Math/Text routers
- `generate(..., max_new_tokens=)` override on Qwen + GLM clients
- LayoutArtifact: `layout_artifact.py` → `data/pdf_pages/<stem>/layout.json`; CLI `--reuse-layout`
- Single-instance: `pipeline_lock.py` + `output/.ocr_pipeline.lock`; CLI `--allow-concurrent`
- Tests: `test_layout_artifact`, `test_pipeline_lock`, greedy/factory token defaults, CLI flags — 16 passed in subset
- Not committed yet (await user)

## 2026-07-23 — Commit greedy / VRAM / TABLE_ROUTER package
- Scoped commit: greedy decode, `layout.release` docker stop, TABLE_ROUTER linear + segmenter/integrity/content-first defenses, `temperature: 0.0`, related tests, planning docs + `handoff.md`
- Excluded: OneDrive phantom M files (empty numstat), `homelab/`, pytest/golden report artifacts, `.cursor/`
- User chose priority 1 from handoff next-actions
- Landed as `e6bcca7`

## 2026-07-23 — MCP overlap check (pre-install)
- Reviewed 14 unique MCP candidates vs existing Qdrant on B.
- Do **not** add Chroma/Cognee/Mengram alongside Qdrant for exam/memory.
- Prefer: context7 + zero-search + codebase-memory + gpu-mcp; keep qdrant read-only.
- Details: `findings.md` § MCP candidate overlap review.

## 2026-07-23 — awesome-agent-skills triage
- Inventory: Cursor skills-cursor (~19), `.cursor/skills` (gstack + planning-with-files + Matt Pocock + HF/eval/Qdrant), `.claude/skills` (gstack mirror).
- Already covered vs VoltAgent list: gstack, hamelsmu eval/RAG, HF trainers, qdrant-search-quality, planning-with-files.
- Recommend install (gap-fill): anthropics|openai pdf, trailofbits modern-python + insecure-defaults, openai security-threat-model, openai jupyter-notebook, pytest-skill, mcp-builder, kreuzberg (alt extract), scientific-skills, tutor-skills, obra systematic-debugging, varlock (secrets).
- Skip for now: megatron farm, web UI stacks, marketing/crypto, Azure-heavy SDKs.

## 2026-07-23 — Installed skills (P0 + named)
Via `npx skills add … -g -a cursor -y --copy` → `~/.agents/skills`, then copied into `~/.cursor/skills` for Cursor discovery:
- `pdf` (anthropics/skills)
- `mcp-builder` (anthropics/skills)
- `modern-python` (trailofbits/skills)
- `insecure-defaults` (trailofbits/skills)
- `varlock` (wrsmith108/varlock-claude-skill)
- `systematic-debugging` (obra/superpowers)
- `pytest-skill` (LambdaTest/agent-skills)

## 2026-07-24 — Task 5: Ingest pageir_v2 + crop_path (done)
- Brief: `.superpowers/sdd/task-5-brief.md`
- Scope: `homelab/ingest/ingest.py` + `tests/test_ingest_figures.py` only
- TDD RED: 2 failed (`pageir_v1`, missing `crop_path`)
- Implemented: CHUNK_VERSION pageir_v2; crop_relpath→crop_path; payload optional crop_path
- GREEN: `uv run pytest tests/test_ingest_figures.py -q` → 2 passed
- Report: `.superpowers/sdd/task-5-report.md`; no commit

## 2026-07-24 — Task 5: Ingest pageir_v2 + crop_path (start)
- Brief: `.superpowers/sdd/task-5-brief.md`
- Scope: `homelab/ingest/ingest.py` + `tests/test_ingest_figures.py` only
- TDD: wrote failing tests for CHUNK_VERSION=pageir_v2 and crop_path mapping

## 2026-07-22 21:07 — dual-PC design review iteration 2
- Reviewed the updated design at `~/.gstack/projects/pdf-scaner/a1217-main-design-20260722-210437.md`.
- Iteration-1 changes are present: Tailnet/API-key posture, DONE contract, Samba-only, A-side embedding, Snapshot API, MCP read-only guidance, Wave-2 gates, and B resource budget.
- Remaining blockers are documented in `findings.md`: atomic sync/publication, precise manifest/key/backup/network implementation contracts, Qdrant Point-ID validity, and A-side resource controls.
## 2026-07-29 — Cross-year error.txt debugging start

- Read `handoff_ocr.md`, planning files, and user-reviewed `error.txt`.
- Replayed region detection from saved `.lines.json`; no GPU/VLM run.
- Generated 14 affected-page overlays under `output/missing_question_overlays/`.
- TDD RED command: `uv run python -m pytest tests/test_dse_mcq_region.py tests/test_mcq_stage3_sanitize.py -q`
  → **4 failed, 23 passed**, each failure matches one confirmed root cause.
- TDD GREEN: regioner/prompt focused suite **27 passed**.
- Rebuilt affected layouts from saved lines in foreground; every 2012--2023 layout
  now has exactly Q1--Q45, no duplicate qids.
- Visual post-fix checks: 2020 Q8--Q11 and 2017 Q31/Q32 boundaries are correct.
- modern-python: Ruff pass, ty pass, full pytest **247 passed** (one external
  Surya/Pydantic deprecation warning).
- Aligned `PipelineManager(nup_enabled=False)` with locked YAML/handoff behavior;
  this resolved two pre-existing full-suite failures.
- VLM OCR was not rerun; old txt/jsonl remain unchanged pending user overlay review.
- User overlay follow-up: repaired orphan crop left gutter and page-leading top
  bound; refreshed 2017/2018/2020/2021 layouts and fixed overlays.
- Visual checks now include full qids/stems for 2017 Q4, 2018 Q4/Q7,
  2020 Q1/Q4/Q7/Q37, and 2021 Q4/Q8.
- Final verification after bbox follow-up: Ruff pass, ty pass, full pytest
  **248 passed** (same external Surya/Pydantic warning).

## 2026-07-29 — 2022 Q1/Q5 and 2021 Q40 overlay refresh

- Read-only replay showed current bboxes at x1=197 for 2022 Q1 and x1=152 for
  Q5, aligned within 0--3 px of the other questions on each page.
- Rebuilt the 2022 layout visibly from cached RapidOCR lines: **4.03 seconds**,
  **45/45**, **0 incomplete**; no VLM/Stage2 run.
- Refreshed fixed overlays for 2022 Q1/Q5 and 2021 Q40. Visual inspection
  confirms all three printed qids are inside their question boxes.
- Root cause was stale generated artifacts. No regioner change was needed.
  Retained the broad right edge to avoid clipping diagrams/right-side choices.

## 2026-07-29 — Instructor structured MCQ Stage2 shadow mode

- Confirmed the trunk uses direct local Transformers `model.generate()`;
  Instructor cannot patch it. Preserved Qwen3-VL 4-bit as the official Stage2
  path.
- Added Pydantic v2 `McqOcrResult` with exact A--D choices, visible figure
  labels, uncertain tokens, warnings, and deterministic review flag.
- Added optional OpenAI-compatible `instructor.from_provider` backend with at
  most one validation retry. Default remains disabled and shadow mode true.
- `question_id` is excluded from the schema and supplied only to deterministic
  `render_text()` from Stage1 block metadata.
- `questions.jsonl` keeps legacy `text` and adds nullable `structured_ocr`;
  incomplete Q1--Q45 coverage now emits a pipeline warning without blocking
  partial draft/smoke runs.
- TDD RED: missing `ocr_pipeline.mcq_structured`; GREEN: 14/14 new tests.
- Verification: 40 focused regressions and full pytest **262 passed**; Ruff and
  ty pass. The only full-suite warning is the existing external
  Surya/Pydantic class-config deprecation.

## 2026-07-29 — Python cleanup

- Removed approved one-off, superseded, legacy `draft.jsonl`, and GLM Python paths.
- Removed dead compatibility aliases and the no-op `polish_per_page` API/config.
- Updated active docs and tests; retained N-up and configured optional OCR engines.
