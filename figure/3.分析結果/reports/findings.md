# Findings & Decisions

## 2026-07-31 — OpenCode handoff package
- OpenCode cannot consume Cursor/Codex skills or MCP wiring → export must be code + plain design docs only.
- Synthesized: `DESIGN_DIRECTION` / `ARCHITECTURE` / `CURRENT_STATUS` + `GENERATE_AGENTS_PROMPT` so OpenCode writes its own `AGENTS.md`.
- Zip paths: project root `pdf-scaner-opencode.zip` and Desktop same name (~400KB; no PDF/data blobs).

## 2026-07-28 — Deploy sherif1313/Arabic-Qwen3.5-OCR-v4 (isolated)
- HF: https://huggingface.co/sherif1313/Arabic-Qwen3.5-OCR-v4 — **Arabic** OCR finetune of **Qwen3.5-0.8B** (~0.9B), not CJK/math DSE VLM.
- Needs **transformers≥5.3** (`Qwen3_5ForConditionalGeneration`); trunk pins `transformers<5` (MinerU) → **`.venv-arabic-ocr` only**.
- Deploy: `2_生產線/_script/deploy_arabic_qwen35_ocr.ps1` + `requirements-arabic-qwen35-ocr.txt` + `2_生產線/_script/smoke_arabic_qwen35_ocr.py`.
- Smoke on 2015p2 Q1 crop: loads OK; output garbled / incomplete (`A.` + Arabic digits) — **not suitable as trunk Stage2**.
- Do **not** swap `2_生產線/config/ocr_pipeline.yaml` default away from Qwen3-VL-8B.

## 2026-07-28 — Emit polish: QID outside math + A–D line breaks
- **`$4. 0.002=$`:** `_partition_math_and_prose` peeled stem opener, but also mis-peeled decimals `0.002` → require `(?!\d)` after dot; `normalize_mcq_block_text` unwraps leading `$N. …$`.
- **Glued options:** `_INLINE_OPTION` inserts newline before mid-line `A./B./C./D.`.
- Offline re-finalize: quality still **pass**; tex openers **45/45**; txt chunks **45** with line-start ABCD **45/45**; `$4.` gone.

## 2026-07-27 — MCQ segment merge → quality pass
- **Cause of fail:** PageIR atomized MCQs (`1.` / `若` / bare math / `A.`) → `pct_le3≈0.40`, `pct_ge20≈0.15`.
- **Fix:** `coalesce_mcq_segments` on MCQ-like pages merges each `N.`…A–D block into **one PROSE** segment (after option-fragment glue). Non-MCQ pages unchanged.
- **Verify (offline re-finalize from jsonl):** `n_segments=45`, `pct_le3=0`, `pct_ge20=1`, `admitted_est=1` → **verdict=pass**.

## 2026-07-27 — Stage2 options “missing”: chunk split, not Qwen3 unread prompt
- **User hypothesis:** Qwen2.5-style long prompt → Qwen3 unread/misread.
- **A/B smoke (Q1 crop):** `MCQ_ROUTER` / `TEXT_ROUTER` / short EN/ZH / cookbook `"Read all the text…"` **all** returned full A–D. Chat path OK.
- **Evidence:** `2015p2.mcq.txt` already had **34/45** ABCD; `questions.jsonl` had stems only because `split_question_chunks` split on *any* `\n\n` — VLM blank lines between stem and `A.` orphaned options (jsonl mapped stem-only; finalize still kept full body).
- **Fix:** split only on `\n{2,}(?=\d{1,2}[\.．])`; shorten `MCQ_ROUTER_PROMPT` (Qwen3 cookbook style, no `LATEX_MATH_RULES` wall). Rebuilt jsonl → **34/45** ABCD.
- **Still open:** ~11 questions without full A–D in Stage2 OCR (re-run with short prompt may help).

## 2026-07-27 — MCQ Stage3 sanitize + fidelity prompts (once-fix)
- **Decision:** Stage2 crop text is source of truth for MCQ emit; Stage3 default `pipeline.mcq_stage3: sanitize` (pylatexenc `unknown_char_policy='keep'` per Context7 `/phfaist/pylatexenc`) — **no VLM rewrite**.
- **Prompts:** `MCQ_ROUTER_PROMPT` (Stage2 when `meta.question_id`) + `MCQ_POLISH_PROMPT` (optional `mcq_stage3: vlm`) — forbid 解題／故／答案為; require keep A–D.
- **Emit:** `render_page_ir` inserts blank line before `N.` openers; `coalesce_mcq_segments` must not glue next stem onto option.
- **Config:** `max_new_tokens_route: 1536` for fuller stem+A–D crops.
- **Why not VLM polish default:** 2015p2 Qwen3 per-Q polish invented solutions and dropped options (~10/45 ABCD in jsonl).

## 2026-07-27 — Post-run check: 2015p2.mcq (Qwen3, per-Q polish)
- **Run OK:** exit 0; wall **1h15m** (route≈701s · polish≈3796s); `questions.jsonl` **45/45**.
- **Quality still fail:** `pct_le3≈0.36`, `pct_ge20≈0.17`.
- **Separation half-fixed:** no longer “D.+next stem on same line” as primary failure mode for early pages; many Qs have lone `N.` lines. But finalize still drops/mangles some stems in `.tex` (**missing openers:** 9,11,29,32–34,45; Q31 glued on one line with A–D).
- **Content regression (main):** Stage3 invents **worked solutions** (Q3/Q6/Q7/Q12…) and often **drops A–D**. jsonl ABCD-complete ≈ **10/45**; many rows are stem-only or solved prose. `.tex` still has ~38 A–D blocks (from segments that kept options), so tex ≠ faithful jsonl.
- **jsonl is polished text** (`_write_questions_jsonl` maps polished chunks by qid); weak jsonl = weak per-Q polish, not Stage2 alone.
- **Next levers:** MCQ-faithful polish prompt (no solve); prefer Stage2 crop text + light sanitize for emit; harden finalize so blank-line/`N.` boundaries survive segmenter.

## 2026-07-27 — Per-question emit + pylatexenc at polish
- **Hypothesis confirmed:** glued/missing options in `.tex` from page-level Stage3, not bad MCQ boxes.
- **Fix at source:** `DraftAssembler.stitch` (all blocks have `question_id`) emits `N.` + `\n\n`; `FinalPolisher.polish` splits those chunks and VLM-polishes each; pipeline writes `*.questions.jsonl`.
- **pylatexenc:** Unicode→LaTeX **after** VLM (`encode_unicode_outside_math`); cannot be “used by” the model — deterministic assist only. Scripts via existing helper first, then `unicode_to_latex(non_ascii_only=True)` outside `$...$`.

## 2026-07-27 — Trunk VLM → Qwen3-VL-8B-Instruct
- HF: https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct — needs recent transformers (`Qwen3VLForConditionalGeneration`); main `.venv` has **4.57.6**.
- Wired: `2_生產線/config/ocr_pipeline.yaml` + `vlm_client._load_causal_vlm` + factory label `Qwen3-VL`.
- Smoke OK: 4bit load, text `OK`, Q2 crop OCR `2`. Still greedy decode (`temperature: 0.0`).

## 2026-07-27 — Docling as layout candidate (user link)
- Project: [docling-project/docling](https://github.com/docling-project/docling) — PDF→DoclingDocument; layout via **Heron** (RT-DETR OD: para/table/figure/header…); TableFormer; OCR; optional VLM (GraniteDocling).
- Fit vs our KPI (**1 MCQ = 1 box**, 題號+A–D): Docling is **general page-element layout**, not exam-question regioner. Likely same class of miss as MinerU/Surya/DocLayout (symbol shreds / no MCQ semantics).
- Grill lock still: specialized Paper2 rules, not swap general DocLayout packages. Current tex glue root cause is **page stitch+polish**, not missing a better general layout model.
- Optional later: one-page bakeoff overlay only if user wants evidence; do not replace `dse_mcq_region` as trunk without that.

## 2026-07-27 — Debug: “題目黏連／缺選項”不是 layout 切錯（2015p2.mcq）
### Evidence
1. **Layout**: `layout.json` 有 **45** 獨立 TEXT boxes（Q1–45）；overlays（如 p3）Q6/Q7 分框清楚；crops 皆存在。
2. **Stage2**: run log **45 route + 45 done**（每題一張 crop、一次 VLM）。Q2 crop 影像本身含 `2.` + 題幹 + A–D。
3. **最終 .tex**: 同頁題被黏成一行／丟題號／丟選項（例：Q1 的 D 與 Q2 題幹同行；Q6/Q7 無獨立題號分隔）。
4. **組裝路徑**: `route_page`（逐題）→ `DraftAssembler.stitch`（**整頁** blocks 拼成一個 draft）→ `FinalPolisher.polish`（**整頁**再 VLM，無圖）→ `finalize_content_first`（按頁拼 .tex）。**沒有**「每題寫完空行 + 題號」的輸出契約；也未把 Stage2 逐題 raw 存成 jsonl。

### Root cause（hypothesis, confirmed by data flow）
- 使用者看到的「連在一起／缺選項」主要來自 **page-level stitch + Stage3 page polish 重寫**，不是 MCQ region 把兩題切進同一框。
- Layout 仍可能有次要問題（例：Q18 orphan `x1=307` 偏右），但無法解釋「45 框都在、crop 有 A–D、tex 卻黏／缺」的主現象。

### Desired fix direction (user)
- 輸出時每題空行分隔 + 寫題號；VLM 45 圖應對 45 題；考慮 **per-question emit**（甚至 per-question polish），勿整頁 polish 融掉邊界。

## 2026-07-27 — Empty-page polish echoed LATEX_MATH_RULES into .tex
- Symptom: compile showed `分數：禁止 a/b…` (prompt chrome, not exam).
- Cause: 2015p2 page 1 has 0 blocks; Stage3 polished empty draft → model dumped `prompts.LATEX_MATH_RULES`.
- Fix: `FinalPolisher.polish` skips blank drafts; rejects multi-marker rules echo (keep draft); pipeline also skips empty `pr.draft`. Cleaned existing `2015p2.mcq.{tex,txt}` prefix.

## 2026-07-27 — First VLM pass on 2015p2 MCQ layout
- `--reuse-layout --output-tag mcq` → exit 0 (~784s; route 311 + polish 466).
- Artifacts: `3.分析結果/output/2015p2.mcq.{tex,txt,pageir.json,quality.json}`
- Quality: **fail** (pct_le3=0.41) — layout KPI only for now.
- Draft caveat: page 1 has **0 MCQ boxes** (cover); Stage3 polish dumped LaTeX style rules into the head of `.tex`/`.txt`. Real MCQ text appears from page 2 (Q1+) but segments are still noisy (glued options / incomplete stems).

## 2026-07-27 — Q36/Q39 diagram bottom clip (last-on-page)
- Mid-page questions get y2 from gap-to-next stem; **page-final** MCQs (2015 p12 Q36, p13 Q39) only had D + `below_options_pad_px` → axis/curve tails looked clipped.
- Fix: after gap snap, set last region `y2 = max(y2, page_h - footer_margin_px)` with `footer_margin_px=160` (above footer chrome ~y=2222 on 2339px pages).
- Evidence: y2=2179; figure-side pad-below-ink ≈180px (Q36) / ≈250px (Q39). Do **not** drop margin to 100 — that swallows footer text into the crop.

## 2026-07-27 — Merge fixes: 2016 Q8+Q9, 2012 Q1+Q2 → all 45/45
- **2016 p4:** right-side graph `B.`/`D.` skipped by left_bias → Q9 dropped → Q8 expanded. Fix: options ignore left_bias.
- **2012 p2:** OCR `2.xs` (from `2x^5`) false-opened Q2; real `2.` rejected by increasing ids → Q1+Q2 merged under fake Q2. Fix: reject opener with **Latin letter glued after the dot** (`2.xs`), but allow `1. Find…` / `11．設`.
- Rebuild from cached lines: **2012/2013/2015/2016 all 45/45**, 0 incomplete. Tests 13 passed.

## 2026-07-27 — 2016p2 p4 was merge not miss (Q8+Q9)
- User correction: Q8 and Q9 boxed together; Q9 not absent.
- Cause: graph MCQ put `B.`/`D.` on **right** half → `left_bias` skipped them → Q9 incomplete → dropped → Q8 y-expand swallowed Q9.
- Fix: option anchors **no longer require left bias** (stems still do).
- After rebuild: **2013/2015/2016 = 45/45**; **2012 = 44** (still missing Q1 only; Q38 recovered).

## 2026-07-27 — Multi-year layout bakeoff (2012/13/15/16)
| Doc | Boxes | Missing | Notes |
|-----|------:|---------|-------|
| **2015p2** | **45** | [] | pass |
| 2012p2 | 43 | **1, 38** | p2 starts at Q2; p13 jumps 37→39 |
| 2013p2 | 44 | **32** | p11→p12 gap 31→33 |
| 2016p2 | 44 | **9** | p4 has 8 then 10 |
| All | — | — | **0 incomplete** after harden rules |

Artifacts: `1_收集資料/data/pdf_pages/<year>/layout.json` + `3.分析結果/output/dse_mcq_layout_<year>/`

## 2026-07-27 — Layout rules hardened (2015p2 → 45/45)
- Fixes vs prior 48-box run:
  1. `question_id_min/max` — reject `0.002…` false opener
  2. `require_increasing_ids` — reject mid-stem Roman `I.`→`1.` / stray `2.`
  3. `drop_incomplete` — omit boxes without ≥3 A–D
  4. `recover_orphan_options` — invent next qid for orphan A–D (recovers **Q18**)
  5. preamble only pulls OTHER lines (does not swallow orphan options)
- Rebuilt from cached RapidOCR lines: **15 pages, 45 questions, 0 incomplete, qids 1–45 contiguous**
- Tests: `test_dse_mcq_region` + profile → **12 passed**
- Artifacts: `1_收集資料/data/pdf_pages/2015p2/layout.json`; overlays `3.分析結果/output/dse_mcq_layout_2015p2/`

## 2026-07-27 — Full 2015p2 MCQ layout (stage: layout-first)
- Script: `2_生產線/_script/dse_mcq_layout_doc.py` (RapidOCR → regions → multi-page `layout.json`)
- Output: `1_收集資料/data/pdf_pages/2015p2/layout.json` (source=`dse_mcq_region:math_cp_p2`); MinerU backup `layout.json.bak_mineru`
- Debug: `3.分析結果/output/dse_mcq_layout_2015p2/` (per-page lines + overlays + `summary.json`)
- Counts: **15 pages, 48 boxes**; expected MCQ **1–45**
- Coverage issues:
  - **Missing Q18** (p6 ends 16–17, p7 starts 19)
  - **False openers:** qid `0` on p3; duplicate `1` on p9/p13; duplicate `2` on p11
  - **4 incomplete** (no A–D): p3/q0, p9/q25, p11/q2, p13/q37
  - p1 = 0 regions (cover/instructions — OK)
- p4 still good (8–11). Next layout polish: reject incomplete/false qids; recover Q18; prefer monotonic qid sequence

## 2026-07-26 — Smoke: 2015p2 page 4 MCQ regions
- Input: `1_收集資料/data/pdf_pages/2015p2/page_004.png` (scan; no PDF text layer)
- Lines: RapidOCR (`uv run --with rapidocr-onnxruntime`) → `3.分析結果/output/dse_mcq_smoke_2015p2_p4/lines.json` (46 lines)
- Truth: **Q8–Q11** (4 MCQs). Detector: **4 regions**, all A–D, `incomplete=false`
- Artifacts: `layout.json`, `overlay.png` under `3.分析結果/output/dse_mcq_smoke_2015p2_p4/`
- OCR quirks fixed: lone `8.`/`A.` (`\s*`); preamble before number; D same-row value; y-expand to next Q (figures)
- Residual: Q8 may clip far-right of graph; `try_run_light_ocr` still stub (smoke used one-off script)

## 2026-07-26 — DSE MCQ region TDD shipped (no commit)
- Plan: `3.分析結果/docs/superpowers/plans/2026-07-26-dse-paper2-mcq-region.md`
- Modules: `dse_mcq_{types,profile,region,layout,ocr}.py` + `2_生產線/config/profiles/math_cp_p2.yaml` + `2_生產線/_script/dse_mcq_regions.py`
- Tests: 9 passed (`test_dse_mcq_*`); ruff clean on touched files
- Code-review (inline vs working tree): Spec mostly met; gaps = PP-OCR stub, no figure-contour expand, no “nearby options” soft reject beyond left-bias
- ohm-mcp: region complexity reduced via helpers; layout “duplication” = false positive on signatures
- B next: implement `try_run_light_ocr` with PaddleOCR/PP-OCR on Ubuntu → dump lines JSON or call directly

## 2026-07-26 — Design approved: DSE Paper2 MCQ 1題1框
- User confirmed shared understanding.
- Spec: `3.分析結果/docs/superpowers/specs/2026-07-26-dse-paper2-mcq-region-design.md` (Approved)
- Path: B light OCR + 題號/A–D rules → question ROI `layout.json` → A VLM `--reuse-layout`
- Reuses `layout_artifact` v1; `block_type=text`; profile `math_cp_p2`; MinerU fallback per page on empty/fail

## 2026-07-26 — Grill: DSE Paper2 1題1框 (in progress)
- Ideal: **1 MCQ = 1 layout box** (full stem + A–D). User strongly agrees.
- Approach locked: **specialized DSE Paper2 MCQ question-region rules** — not “swap another general DocLayout”.
- Why: PP-DocLayout / MinerU cut by paragraph/formula/figure, not by question number → over-fragment → many VLM calls → high `pct_le3`.
- Existing `assemble.coalesce_stitched_fragments` / `segmenter.coalesce_mcq_segments` insufficient for instruction shreds + formula atomization.
- Pipeline hook locked **A**: page image / light line detect → question ROI crops → one VLM call per question (bypass MinerU fine boxes on Paper2 path).
- Boundary signals locked **B**: question-number opens a region; **A–D option anchors** confirm/close a full MCQ (avoids false splits on in-stem `1.` / bare digits).
- Subject scope locked **C**: v1 validate **MATH CP Paper2** only; implement as extensible subject profiles.
- Dual-column locked **C**: v1 single-column; dual-column detect as profile flag default **off**.
- Anchor OCR host locked **A**: **B** light OCR (PP-OCR / line detect) → question ROIs + `layout.json`; **A** VLM only (`--reuse-layout`).
- Figures locked **A**: diagram stays inside the same question ROI (still 1 box / 1 VLM call).
- v1 success locked **C**: prove **box correctness** first (count ≈ truth; most boxes contain stem+A–D); quality gate is next-stage KPI.
- **Grill closed pending user confirm** of shared understanding in `task_plan.md` Next Action.
- **Confirmed** 2026-07-26; design written (see above).

## 2026-07-26 — OCR quality gate implemented (TDD)
- Issues #4 (core) + #3 (wiring); Copilot assign **failed** (`Bot does not have access`) → local TDD
- Module `ocr_pipeline.quality`; ingest/batch flags; finalize emits `.quality.json`
- Focused tests 29+ green; ruff clean on touched files; ohm `analyze_codebase` on quality: 0 issues
- Offline `nup-v2`: fail (le3=0.277, ge20=0.225, admitted_est=0.533)

## 2026-07-26 — N-up gate temporarily disabled
- User will manually flatten dual-layout PDFs to single-page; `nup.enabled: false` in `2_生產線/config/ocr_pipeline.yaml`
- Code path kept; re-enable when needed

## 2026-07-26 — Quality gate implemented (TDD; Copilot assign failed)
- Issues: [#4](https://github.com/keith1011/pdf_converter/issues/4) core, [#3](https://github.com/keith1011/pdf_converter/issues/3) wiring
- Copilot assign: GraphQL `Bot does not have access` — implemented locally
- `ocr_pipeline.quality` + ingest/batch flags; finalize emits `.quality.json`
- Tests: quality admit/report + ingest gate — green; ruff clean on touched files
- ohm-mcp: analyze_codebase on quality.py (no high issues)
- Offline nup-v2: verdict **fail** (le3=0.277, ge20=0.225, admitted_est=0.533)

## 2026-07-25 — nup-v2 Stage2 ~45s/block (EOS / token burn)
- Symptom: `nup-v2` Stage2 avg ~38–46s/block (flat); died mid `p007_v0_b007` after ~2h. Compare `nup-full` ~1–5s after warmup.
- Timing math: ~45s ≈ burning `max_new_tokens_route=1024` at normal tok/s — not “more pages”.
- Stub-prompt probe (“Transcribe…”) → `n_new=1024`, wall of `!` (~63s). **Real** `TEXT_ROUTER_PROMPT` on same crops → early stop (~2–4s, n≈18–67).
- Hung crop `p007_v0_b007` retested OK with real prompt; root cause of *why* that run missed EOS not fully reproduced (env / stop-id set).
- Hardening: prefer `generation_config.eos_token_id` **list** (`[im_end, endoftext]`) over tokenizer single id; WARN when `n_new >= 0.9 * max`.

## 2026-07-25 — Full nup-full analysis (before fix decision)
- Full OCR exit 0 (~843s): `3.分析結果/output/2014-DSE-MATH-CP-2.nup-full.*`
- Split OK: p2/p3/p5/p8 `2_lr`, layout `v0→v1` no flips
- **Missed true 2-up:** p4 (booklet 6–7), p6 (10–11), p7 (12–13) — classifier `1`/`uncertain`; v_score 0.04/0.48/0.10
- Hypothesis: diagram-heavy / uneven ink → mid gutter signal weak vs content bands
- GPU peak ~9GB during run; idle ~2GB after

- User scope lock: **B = 2-up + 4-up (2×2)**; 8-up deferred.
- Flow intent: coarse split → one PNG per version → MinerU per version → existing Qwen path.
- Uncertain N-up: **A = fall back to whole page as single-version MinerU** (safe; may reintroduce interleave).
- Coarse split method: ~~XY-Cut++ primary~~ → **revised: classifier + fixed geometric cut** (midline / 2×2 grid).
- Version labels: **B = try semantic** (EN/ZH, Ver A/B); fall back to `vN` if unsure.
- Default mode: **B = auto-detect** (split when 2/4-up looks confident; else single-page path).
- Architecture pick: **Approach C** — N-up **classifier** → fixed crop (L/R or 2×2) → MinerU per panel → existing Qwen path. Tradeoff: simplest; skew/uneven gutters brittle.

### Locked decisions (brainstorm)
| Topic | Choice |
|---|---|
| N-up scope | 2-up + 4-up (2×2); 8 later |
| Uncertain split | Fall back whole-page MinerU |
| Coarse splitter | **Classifier + fixed midline / 2×2 grid** (not XY-Cut++) |
| Version IDs | Semantic if possible, else `vN` |
| Enablement | Auto-detect smart mode |
| Pipeline shape | Pre-crop gate (Approach 1 shape) with C-style cut |

### Approved artifacts
- Spec: `3.分析結果/docs/superpowers/specs/2026-07-25-nup-classifier-crop-design.md`
- Plan: `3.分析結果/docs/superpowers/plans/2026-07-25-nup-classifier-crop.md`
- Classifier MVP in plan: **projection-valley heuristics** (CPU, no extra VRAM), not a trained N-up CNN.
- Implementation (2026-07-25): modules `nup_{types,crop,classify,router,merge,label}`; pipeline Stage1 via `analyze_page_with_nup`; config `nup.enabled=true`; PageIR `version_id`; polish splits on `<<<nup:…>>>`. Tests `-k nup` → 20 passed.
- Classifier fix post-smoke: dark-spine + landscape→prefer `2_lr` (booklet crease). `confidence_threshold: 0.70`. GPU smoke limit-3 exit 0.
Not a drop-in “better than MinerU for DSE dual-version” winner; problem splits into **detection** vs **reading order**.
- **Detection:** DocLayout-YOLO (real-time, DocStructBench); PP-DocLayout family; MinerU already on PP-DocLayoutV2. Newer **PP-DocLayoutV3 / RT-DocLayout** claims detection+seg+reading-order unified.
- **Reading order:** classic XY-Cut weak on complex multi-col; **XY-Cut++** (2025) strong on order recovery (papers claim large gains vs XY-Cut / LayoutReader) — complementary to detectors, not a replacement.
- **End-to-end VLM OCR:** olmOCR 2 / DeepSeek-OCR — better multi-col *linearized text*, different product (less PageIR/crop control).
- For our pains (dual-version columns + MCQ atomization): order algorithm / region merge > swapping detector alone.
**Root cause:** MinerU atomizes MCQs (2014 p2: 39 blocks, 23 formula/equation). Stage2 OCR per tiny crop → stitch `\n\n` → segmenter → PageIR **45% segments ≤3 chars** (`A.` / `-1` / `。`).

**Research:** Qwen2.5-VL OCR best practices (DeepWiki) — specific prompts, preserve structure, don’t fabricate; Alibaba VL-OCR — explicit “do not omit/fabricate”.

**Fixes shipped:**
1. `TEXT_ROUTER_PROMPT` / polish / figure caption — exam MCQ structure + no-fabricate + less eager「細節不清」.
2. `coalesce_stitched_fragments` in `DraftAssembler.stitch`.
3. `coalesce_mcq_segments` at end of `segment_stitched_page`.
4. Tests: `2_生產線/tests/test_mcq_coalesce.py` (+ segmenter/content_first) **27 passed**.

**Needs re-OCR** for 2014 (or any doc) to refresh outputs; offline segmenter alone can’t fix already-written txt without re-run.

## 2026-07-24 — Gated column-major reading order
- Added `reading_order.py`: detect two-column (gap + separated centers; ignore wide banners) → column-major; else row-major `(y1,x1)`.
- Wired into MinerU, DocLayout-YOLO, and `load_layout_artifact` (so `--reuse-layout` also benefits).
- 2014 check: page1 `row_major`; pages2–8 `column_major` with **1** L→R flip (was 7–23).
- 2012/2013/2015/2016: expect mostly `row_major` (verified in session).
- Re-OCR 2014 with `--reuse-images --reuse-layout` to refresh txt/tex/pageir.

## 2026-07-24 — 2014 dual-version L/R reading order bug
User: 左右分版；現在讀成左→右交錯（如 16 題第一行 → 19 題第一行 → 16 題第二行）。

**Root cause:** `mineru_layout.py` sorts blocks with `(bbox.y1, bbox.x1)` then reassigns `order`. Same-y left+right → LTR zigzag across columns.

**Evidence (layout.json):** page2 has **23** L/R order-flips; e.g. order0 L, order1–2 R, order3 L… Page1 is single-column-ish (all R, 0 flips) — cover/instructions on one side.

**Fix direction (not implemented yet):**
1. Detect 2-column (x-gap / bimodal cx); sort **column-major**: all L by y, then all R by y (or configurable).
2. Or emit two PageIR streams / two docs (version A / B) when dual-version detected.
3. Same sort exists in `doclayout_yolo.py` — fix both if changed.

## 2026-07-24 — Applied context7 VLM hardenings (post-kill)
- `resolve_stop_token_ids` + `build_generation_kwargs(..., eos/pad)` wired into `run_vlm_generate`.
- `force_greedy_generation_config` on Qwen/GLM load (clears temperature/top_p/top_k → stops ignored-flag warn).
- Stage2: `route` + `done <id> Xs` with `flush=True` so long generates are visible.
- Hard generate timeout **not** added (CUDA generate not cancel-friendly on Windows); rely on EOS stop + timing.
- Focused tests: **10 passed** (`test_vlm_greedy_decode` + `test_skip_figures_router`).

## 2026-07-24 — Code check during 5-doc smoke (context7 + vlm_client)

Against transformers **v4.57** docs + Qwen2-VL README (via context7):

1. **Our generate path matches the official Qwen template shape** (`apply_chat_template` → `generate` → trim `input_ids` → `batch_decode`). Good.
2. **Hang risk / slow Stage2:** `build_generation_kwargs` only sets `max_new_tokens` + `do_sample=False`. Docs recommend also setting `eos_token_id` (and usually `pad_token_id`) on `GenerationConfig` / `generate`. If EOS is not honored from model config, greedy decode can burn the full **1024** route tokens per crop → looks “stuck” (no log between `route` lines). Matches the ~50min stall on `2013p2` first text block.
3. **Log noise:** transformers warns `temperature` generation flag ignored — likely from model `generation_config` while we force greedy. Harmless but confirms config mixing.
4. **Processor:** “Qwen2VLImageProcessor loaded as fast by default” warning — behavior change vs older checkpoints; watch for OCR quality drift; can force `use_fast=False` if needed.
5. **Budgets:** Official VL chat demos often use `max_new_tokens=128`; we use route **1024** / polish **2048**. Correct for long exam pages, but Stage2 should log per-block timing and consider lower caps for tiny crops.
6. **`torch.cuda.empty_cache()` after every generate** — safe on 12GB, adds sync cost across hundreds of blocks.

**Suggested follow-up (after smoke, not mid-run):** pass `eos_token_id` / `pad_token_id` from `processor.tokenizer` into `generate`; add Stage2 per-block elapsed log; optional generate timeout.

## 2026-07-24 — Task 7: figure+batch contract (docs + regression)
- `skip_figures=true` → crop FIGURE blocks but **no draft OCR** stitch into Stage2 text (caption path still used when `extract_figures`).
- `extract_figures=true` (default) → figure **caption path**: crop → Qwen caption → `figures/<id>.png` + PageIR `SegmentKind.FIGURE` with `crop_relpath`.
- Ingest `chunk_version=pageir_v2` (UUID5 keys differ from `pageir_v1`; re-ingest needs `--reindex` or leaves duplicate-era points).
- Batch CLI: `uv run python -m ocr_pipeline.batch_export --docs <stem> --publish --ingest --share-root Z:/` (fail-continue unless `--fail-fast`).
- Full regression: **144 passed** (1 Pydantic deprecation warning from surya).

## 2026-07-24 — Task 6: batch_export CLI
- Keep `publish` / `ingest_job` as module-level names (initially `None`) so tests can `monkeypatch.setattr("ocr_pipeline.batch_export.*", ...)`.
- Lazy `_import_homelab()` only when publish/ingest needed; failed publish skips ingest for that doc.
- Milestone rule: `--ingest` requires `--publish` (raises if `job_dir` missing).
- **Fix:** ingest may raise `SystemExit`; per-doc handler must catch `(Exception, SystemExit)` or one bad doc aborts the batch. Preflight also rejects ingest-without-publish.

## 2026-07-24 — Task 5: ingest pageir_v2 + crop_path
- `CHUNK_VERSION` was `pageir_v1`; bump to `pageir_v2` changes UUID5 `point_id` keys (re-ingest needs `--reindex` or leaves duplicate-era points).
- PageIR stores `crop_relpath`; ingest segment dicts / Qdrant payload use `crop_path` (omit when absent).
- Focused tests: 2 passed (`2_生產線/tests/test_ingest_figures.py`).

## 2026-07-24 — Task 4: staging and figure publication
- `publish()` currently flattens every artifact to `src.name`, so nested figure paths cannot be preserved.
- `validate_done_dict()` accepts nested artifact paths but only enforces on-disk listing for optional top-level PageIR/TeX files; `figures/*.png` needs the same completeness check.
- `2_生產線/src/ocr_pipeline/job_stage.py` and figure publish tests do not yet exist.

## 2026-07-24 — Task 3: figure pipeline wiring
- Existing `DynamicRouter` returns skipped FIGURE blocks before cropping; the new contract requires cropping first while keeping `raw_text=""`.
- `finalize_content_first` currently has no figure merge input, and `PipelineManager` does not call `export_figures`; factory only wires `skip_figures`.
- TDD tests now require retained figure crops and `figure_segments_by_page` merging into rendered text/PageIR.

## 2026-07-24 — Task 1: PageIR FIGURE + crop_relpath
- `SegmentKind.FIGURE`, `ContentSegment.crop_relpath` (default None), render `(圖: {text})`, JSON key `crop_relpath`.
- `apply_integrity_to_page` preserves `crop_relpath` on MATH rebuild.
- Focused pytest: 11 passed (`test_page_ir_models` + `test_content_first`).

## 2026-07-24 — Fixed prior trunk gaps (skip_figures / MathRouter / mineru uv)
- `pipeline.skip_figures` → `DynamicRouter.skip_figures` (true: no crop; false: FIGURE via text/VLM).
- `MathRouter`: removed MinerU package probe; requires `formula_engine` or `vlm_fallback`.
- uv: `transformers>=4.49,<5` (was 5.14 — blocked MinerU); group `mineru` + `default-groups=["dev","mineru"]`.
- Main `.venv`: `import mineru` OK (3.4.4). PP-DocLayoutV2 is torch/transformers, not paddle.
- Full `uv run pytest`: **127 passed**.

## 2026-07-24 — modern-python code check: MinerU + Qwen + Qwen trunk
- **Wiring OK:** `load_ocr_config()` → `MineruLayoutEngine` + `VlmTextEngine` + `VlmFormulaEngine` + `Qwen25VlClient` (polish).
- **Fixed earlier:** factory default `layout=mineru`; MinerU figure labels → `FIGURE`.
- Prior “still open” items above are now closed.

## 2026-07-24 — Trunk stack locked: MinerU + Qwen + Qwen
- User chose default: `engines.layout=mineru`, `text=vlm`, `formula=vlm`.
- Rationale: layout bakeoff (equation typing vs DocLayout/Surya) + scorecard (Qwen ≫ mineru-ppocr/got for prose/math).
- Ops: main `.venv` still has no `mineru` import — OCR with this default → `.venv-mineru312` until optional uv group lands.
- `question_paper` mode still skips block layout (content-crop + page VLM).

## 2026-07-23 — uv migrate (modern-python)
- Source of truth: `pyproject.toml` + `uv.lock`; core deps via `uv add`; groups `dev`/`lint`/`test`/`got`.
- Torch CUDA via pytorch-cu126 index (`2.13.0+cu126`, cuda True after re-pin).
- MinerU **not** in main lock (Py3.14 + transformers 5 + fasttext MSVC) — keep `.venv-mineru312`.
- `surya-ocr` still `uv pip install surya-ocr --no-deps` (not locked; uv sync removes it).
- `uv run pytest`: **120 passed**.

## Homelab Wave 1 (2026-07-23) — closed green
- Root cause of SSH block: A pubkey not in B `authorized_keys` until `install-pc-a-key.sh`.
- Backup script must hit `http://$B_LAN_IP:6333` (not loopback); download snapshots via REST, not `docker cp`.
- Evidence: RP `20260723T152007Z`; points 835; reader upsert/delete 403; ufw ENABLED; Wave 2 deferred.

## Homelab Wave 1 blocker (2026-07-23) — resolved
- A→B SSH: host key OK after `StrictHostKeyChecking=accept-new`; auth still **Permission denied** until B installs `Z:\backups\ssh-bootstrap\pc-a.pub` via `install-pc-a-key.sh`.
- No `QDRANT_WRITER_KEY` / `WAVE1_SSH_PASSWORD` in User/Process env on A — ingest + reader neg-test wait on keys in `%USERPROFILE%\.2_生產線\homelab\qdrant.a.env` (generated) + B `apply-qdrant-env.sh`.
- A-side RP pack works without SSH: `RP_ID=20260723T122750Z`, `DONE_count=1` in `jobs.tar.gz`.
- Second job published: `Z:\jobs\20260723-130314-wave1demo` (`doc_id=wave1demo`, 8 segments) — ingest pending key rotation.
- Follow-along path: `2_生產線/homelab/2_生產線/_script/RUN_ON_B.md` + `wave1-on-b.sh`.

## GPU smoke env (2026-07-23)
- Main `.venv` is **Python 3.14** — no `paddlepaddle` wheel; experiment stacks need **Python 3.12** venvs (`.venv-engines312` for GOT, `.venv-mineru312` for MinerU).
- Windows: `torch` CUDA + `paddlepaddle-gpu` **cannot coexist** (cuDNN DLL WinError 127). Use **paddle CPU** for PP-OCR text while DocLayout/GOT/MinerU use CUDA torch.
- GOT: prefer HF-native `stepfun-ai/GOT-OCR-2.0-hf` (no `verovio`); DocLayout load via `hf_hub_download(...pt)` not broken `YOLOv10.from_pretrained`.
- MinerU 3.4.x: needs `transformers<5` (`mineru[pipeline]`); PP-DocLayoutV2 + UniMERNet via `auto_download_and_get_model_root_path`.
- PaddleOCR 3.x: use `predict()` + `rec_texts` (legacy `ocr(..., cls=True)` broken).
- Limit-1 timings (log only): got-ppocr total **33.9s**; mineru-ppocr total **39.2s**. Quality not scored yet — draft Chinese/prose still rough under skip_polish.

## 2026-07-23 — modern-python code check (no full uv migrate)
- Tooling: light `pyproject.toml` + ruff in `.venv`; **no** `uv.lock` / ty / prek. Runtime still `requirements-*.txt` + multi-venv (3.14 Qwen, 3.12 GOT/MinerU).
- Focused engines: ruff found 1 import-order issue (fixed) + 6 format diffs (formatted). pytest **11 passed** (then 9 after format scope).
- Gaps vs modern-python ideal: not on `uv sync`/`uv run`; deps still requirements.txt; `ty` absent; Py3.14 default venv blocks Paddle.
- Verdict: adapter smoke fixes are lint-clean enough to commit; full uv migration is a separate opt-in task.

## Landscape (office-hours 2026-07-22)
- **L1:** Local RAG = Documents→embed→vector DB→retrieve→LLM; don’t expose vector DB to public net; Tailscale/VPN for remote.
- **L2:** 2026 guides push **decouple** embedding / Qdrant / LLM to avoid GPU contention; Qdrant+Ollama compose is common; **DeepTutor** (HKUDS) is a full self-hosted AI-tutor+question-bank stack; multi-agent fails when two writers share Qdrant/files without ownership.
- **L3/EUREKA:** Tutorials co-locate the whole stack on one GPU box. Your split (**A = OCR+teacher LLM, B = Qdrant/MCP/light agent**) is the two-PC version of that isolation—and it protects the 4070 from always-on services. B’s 1660S is for light agent/embed assist, **not** the teacher model.

- **North star / product name:** **P-ocr** = AI 老師 Chat（題庫餵模型）；OCR 只是第一步產資料的工具（舊稱「北辰」已棄用）
- **PC-A (Win):** 9600X + 4070 Super — OCR/VLM + **主力 Chat LLM**（暫定）；成功後再升級本機或租雲端 GPU
- **PC-B (→ Linux):** 5600X + 1660S — **資料真相**（Qdrant + files）+ MCP host + **輕量 LLM agent**（助 A 研發、調資料、agent 協同；非主力老師模型）
- Flow: A OCR/分析 → ingest 到 B 的 Qdrant/檔案 → A Chat 即時查 B；B agent 協助檢索/研發工作流
- **Work topology:** Office PC-C --RustDesk--> home PC-A (Cursor on A); A↔B same switch/LAN primary for Qdrant/Samba; Tailscale for remote ops
- First ship (D7=A): B = Linux always-on NAS + Qdrant storage；检索 UX / 老師 Chat 為後續



## Product bar (locked 2026-07-21)
- Prefer **complete formulas + readable linear text** over marking-scheme tabular layout.
- Ship 1 artifacts: `.tex` + `.txt` + `.pageir.json`
- Ship 1.5: `--check-compile` → sibling `.log` + `.pdf` (keep `.tex` on fail)
- Ship 2: OCR overlay PDF (TODO)

## Root causes fixed this arc

### 1) Markdown leak into final outputs
- **Symptom:** `| --- |`, `<br>` in `3.分析結果/output/123.txt`
- **Cause:** short docs used full-doc polish; polished txt/tex not written to `PageResult`; content-first fell back to Stage2 draft
- **Fix:** always per-page polish; segmenter linearizes Markdown tables / HTML breaks / align|itemize

### 2) CUDA device-side assert (Stage2)
- **Symptom:** `TensorCompare.cu Assertion input[0] != 0` / async report in `_has_unfinished_sequences`
- **True site (`CUDA_LAUNCH_BLOCKING=1`):** `_sample` → `torch.multinomial`
- **Cause:** `vlm.temperature: 0.1` → `do_sample=True` on Qwen2.5-VL 4bit; bad probs
- **Not the cause:** fullpage crop size (same crop greedy OK)
- **Fix:** `build_generation_kwargs` always greedy; config temperature `0.0`

### 3) Stage3 OOM after successful Surya v2
- **Symptom:** polish text-only generate needs ~2.09 GiB; `free: 0`
- **Evidence:** after layout, nvidia-smi ~11GB used by Docker `surya-vllm-*`; torch alloc 0
- **Cause:** `SuryaInferenceManager.stop()` / `VllmBackend.stop()` only clears handles; docker cleanup is atexit-only
- **Fix:** `layout.release()` → manager.stop + `_stop_surya_docker_vlms()` + `_wait_for_gpu_headroom()`
- **Verify:** after_layout ~11GB → after_release ~390MB; limit-1 golden exit 0 + PDF

### 4) Full 14-page golden compile fail (2026-07-22)
- **Pipeline:** exit 12 after OCR wrote `.tex`/`.txt`/`.pageir.json` (~43 min; no Stage3 OOM)
- **Cause:** later pages still emit broken tabular chrome as math, e.g. `$\begin{tabular}...\$$\hline$`
- **Log:** `Missing $ inserted`, `Misplaced \noalign`, `Not in outer par mode`
- **Note:** limit-1 page looked linear; full doc reintroduces table layouts via Stage2/polish
- **Fix (2026-07-23):** segmenter strips `table`/`tabular`/`hline` + `&` rows; `_TEX_MATH_HINT` no longer matches bare `\begin` / bare `\`; `TABLE_ROUTER_PROMPT` → linear (no Markdown/tabular); integrity flags tabular chrome in math; CJK peeled out of `$...$`; junk `\frac{CJK}{-}` / `\caption` dropped. **Offline re-finalize of `3.分析結果/output/123.tex` → `--check-compile` OK (PDF ~101KB).**

## Commits
| SHA | What |
|-----|------|
| `dbd2e02` | Content-first Ship 1 |
| `365c186` | Ship 1.5 `--check-compile` |
| `e6bcca7` | Greedy decode + Surya docker release + tabular compile defenses |
| *(pending)* | Phase 2.8 speed: tokens + LayoutArtifact + single-instance lock |

## Phase 2.8 speed (2026-07-23)

Evidence: full golden `3.分析結果/output/123.tex` ~15KB; Stage1 often 2–3 blocks/page — 4096 tokens wasted decode budget.

| Change | Detail |
|--------|--------|
| Token budgets | `max_new_tokens: 2048` (Stage3 polish default); `max_new_tokens_route: 1024` (Stage2 crops) |
| API | `VlmClient.generate(..., max_new_tokens=)` override; routers pass route budget |
| LayoutArtifact | `1_收集資料/data/pdf_pages/<stem>/layout.json` written after Surya; `--reuse-layout` skips Surya |
| Dual-run guard | `3.分析結果/output/.ocr_pipeline.lock` + live PID; `--allow-concurrent` to override |

If Stage3 starts warning `polish truncated`, raise `vlm.max_new_tokens` before touching route budget.

## Uncommitted (as of 2026-07-23 Phase 2.8)
- Phase 2.8 code + tests + planning docs (not committed yet)
- `2_生產線/homelab/`, `.cursor/`, phantom OneDrive M files, pytest/golden artifacts

## Task 4 wiring (2026-07-23)
- `PipelineManager` currently couples image conversion, `analyze_page`, and `release` to `LayoutAnalyzer`; Task 4 splits this into `layout` (image source) plus `layout_engine` (`analyze`/`release`) while retaining a fallback for existing combined test doubles.
- Existing VLM adapters already expose the required `.ocr(crop_path)` interface. Routers must delegate to those adapters while preserving the table-specific VLM prompt.

## Task 6 PP-OCR text adapter (2026-07-23)
- `TextEngine` is a runtime-checkable protocol with only `ocr(crop_path: Path) -> str`; `EngineError` is the shared explicit-failure type.
- `build_default_pipeline` currently accepts only `engines.text: vlm`; the PP-OCR branch must preserve the existing VLM text and table engines.

## Task 7 GOT + DocLayout-YOLO experiment (2026-07-23)
- `DocLayoutYoloEngine` lazy-loads `YOLOv10.from_pretrained("juliozhao/DocLayout-YOLO-DocStructBench")`; inference boxes are sorted top-to-bottom and labels map to shared `BlockType`.
- `GotFormulaEngine` lazy-loads `stepfun-ai/GOT-OCR2_0` through Transformers remote code and calls `model.chat(..., ocr_type="format")`; dependency, model-load, and inference failures raise `EngineError` rather than falling back to Qwen.
- Mocked CPU tests passed (7). GPU smoke intentionally skipped because `doclayout_yolo` and `paddleocr` are absent; no multi-GB weights were downloaded.

## Task 8 MinerU + UniMERNet experiment (2026-07-23)
- `MineruLayoutEngine` and `UnimernetFormulaEngine` lazy-load their optional dependencies and convert unavailable dependencies, weights, and inference failures to `EngineError`; neither falls back to Qwen.
- Current MinerU UniMERNet source accepts detected formula regions plus a decoded image and returns formula items with `latex`; the adapter treats each formula crop as one display-formula region.
- Factory now accepts `layout: mineru` and `formula: unimernet`, while main retains `surya` / `vlm` defaults. Mocked tests do not download models; GPU smoke remains optional until local caches exist.

## modern-python review (2026-07-23) — Phase 2.8 / ocr_pipeline

Scope: usage freshness & complexity (not a full uv migration). Runtime: **CPython 3.14.6**; `uv` installed globally but project still **requirements.txt + `.venv` + `PYTHONPATH=src`** (no `pyproject.toml`, no ruff/ty in venv).

### Already modern (keep)

| Pattern | Where |
|---------|--------|
| `X \| Y` unions, `list[T]`, `dict` | almost all modules |
| `from __future__ import annotations` | package-wide |
| `pathlib.Path`, keyword-only `*` | pipeline / artifact / lock / routers |
| `Protocol` + dataclasses / Enum | `vlm_client`, `models` |
| `Path.unlink(missing_ok=True)` | `pipeline_lock` |

### Over-complex or stale *usage* (code smell, not “wrong API”)

| Item | Verdict | Note |
|------|---------|------|
| `Qwen25VlClient.generate` ≈ `Glm46VFlashClient.generate` + dual `_resize` | **繁雜** | ~80 行重複；可抽 shared helper，非語法過時 |
| `decide_polish_per_page` always `True` | **死 API** | 相容用，可刪或標 deprecated |
| `pipeline_lock` PID + `tasklist` fallback | **略繁** | 合理無新依賴；若允許依賴可用 `filelock`。`atexit` + 手動 `acquire/finally` 雙軌，pipeline 沒用 `with` |
| `layout_artifact` 手寫 dict | **可接受** | 比 `asdict` 可控；`if not b.image_path` 近乎死碼（Path 幾乎總 truthy） |
| 大量 `print` / bare `except Exception` | **CLI 現實** | ruff T20/BLE 會吵；研發 CLI 可 ignore，不必為「現代」改 logging |
| `factory`/`load_ocr_config` → bare `dict` | **鬆** | 可之後 TypedDict；非阻塞 |

### Tooling vs modern-python skill（專案級，非單一 .py）

- Skill 預設：`uv` + `pyproject.toml` + ruff + ty + `uv run`
- 現況：`requirements-ocr-pipeline.txt` + 手動 venv — **工具鏈偏舊**，但應用碼語法已偏新
- **不建議**現在為 Phase 2.8 整包搬 uv（風險高、與 CUDA/torch 鎖版衝突）；若要現代化，單獨開「tooling」任務

### 建議優先級（若要動刀）

1. P2：抽 VLM `generate`/`_resize` 共用，減繁雜  
2. P3：清 `decide_polish_per_page` 死分支；layout 死碼註解  
3. Backlog：`pyproject.toml` + ruff（不強制換掉現有 `.venv` 跑 GPU）

## Resources
- Content-first design: `~/.gstack/projects/pdf-scaner/a1217-main-design-20260721-153800.md`
- Eng plan: `~/.gstack/projects/pdf-scaner/a1217-main-eng-review-plan-20260721-content-first.md`
- Planning skill: `~/.cursor/skills/planning-with-files/SKILL.md`
- Always-on rule: `.cursor/rules/planning-with-files.mdc`

## Design review iteration 2 (2026-07-22)
- Reviewed `a1217-main-design-20260722-210437.md` against completeness, consistency, clarity, scope, and feasibility.
- Remaining high-risk gaps: atomic B-side job publication/checksum verification; exact `DONE.json` schema; concrete Qdrant reader/writer key configuration; jobs/config backup and restore; Qdrant reachable-only-on-tailnet deployment rule.
- Other implementation gaps: deterministic Point ID must use Qdrant-supported UUID/uint64, and A resource/concurrency budget needs an enforceable limit.

## MCP candidate overlap review (2026-07-23)

User list (15 URLs; `arxiv-latex-mcp` duplicated → 14 unique). Compared against existing **user-qdrant** (B:6333, read-only) + Samba + Cursor native tools.

### Capability clusters

| Cluster | Servers | Verdict |
|---|---|---|
| Vector / RAG store | chroma-mcp, cognee-mcp, mengram, (existing) qdrant | **Hard overlap.** Second vector DB for exam/memory fights single-writer Qdrant on B. |
| Agent long-term memory | mengram, cognee, qdrant `memories`, codebase-memory (code KG only) | Soft conflict — pick ≤1 memory brain besides exam Qdrant. |
| Web get page | fetch, zero-api-key `browse_page` | Overlap; zero supersedes fetch. |
| Web search | zero-api-key-web-search | Unique in list; aligns with future SearXNG on B. |
| Filesystem R/W | filesystem MCP, knowlyr-sandbox, Cursor native | Overlap + write-risk on Samba jobs. |
| Code intel | codebase-memory, GitHub MCP, filesystem | Complementary (mild tool-count noise). |
| Docs grounding | context7 | Unique (library docs). |
| Papers / bib | arxiv-latex-mcp, zotero-mcp | Complementary. |
| Doc convert | mcp-pandoc | Unique; keep out of exam ingest writer path. |
| Code exec | jupyter-notebook-mcp, knowlyr-sandbox | Different jobs; Jupyter is NB 6.x only. |
| GPU metrics | gpu-mcp-server | Unique; no data conflict. |
| GitHub API | servers-archived/.../github | Avoid archived; use maintained GitHub MCP. |

### True conflicts
1. chroma + qdrant for exam/memories → dual truth.
2. cognee + mengram + qdrant memories → multiple memory writers.
3. filesystem MCP write roots on `Z:\` / jobs → bypass DONE.json ingest discipline.
4. fetch + zero browse → duplicate tools / context waste.

### Recommended for PC-A Cursor
- **Now:** context7, zero-api-key-web-search, codebase-memory-mcp, gpu-mcp-server; keep user-qdrant read-only.
- **When needed:** arxiv-latex-mcp, zotero-mcp, mcp-pandoc.
- **Skip/defer:** filesystem, fetch, chroma, cognee, mengram, jupyter-notebook-mcp, knowlyr-sandbox, archived github.

## modern-python cleanup applied (2026-07-23)

Executed in order after review:
1. **Shared VLM path** — `run_vlm_generate` / `resize_image` / `strip_fences` in `vlm_client.py`; `Glm46VFlashClient.generate` delegates
2. **Dead API** — removed `decide_polish_per_page` + auto polish warn; always per-page polish; `--polish-per-page` deprecated no-op; `PipelineLock` context-manager only
3. **Light ruff** — `pyproject.toml` + `requirements-dev.txt`; install with `uv pip install -p .venv ruff` (GPU requirements.txt kept); `ruff check 2_生產線/src/ocr_pipeline 2_生產線/run_ocr_pipeline.py 2_生產線/arrange_only.py tests` clean
## 2026-07-29 — Cross-year MCQ visual QA root causes

- 多數 missing qids 都是 affected page 的第一題；RapidOCR 漏題號但保留 A–D。
  `_recover_orphan_options` 只掃 accepted region 之後的 gap，沒有掃第一個 region 前的 prefix。
- 2020 p4 把 Roman `II.` OCR 成 `11.`；greedy increasing filter 選了 `[8, 11]`
  並丟棄後面的真 Q9/Q10，之後 orphan recovery 錯補成 Q12–Q14。
- 2017 Q31 是 graph-choice 題；RapidOCR 看見明確 `31.`、下一題 `32.`，但 A/C 未讀到、
  D 缺句點，只命中 B，因 `min_option_hits=3` 被 drop。
- `MCQ_ROUTER_PROMPT` 只說公式使用 `$...$`，沒有說明貨幣 literal dollar 必須輸出
  `\$`，與 `error.txt` 多年 currency omission 一致。
- 14 張 pre-fix debug overlays 已集中在 `3.分析結果/output/missing_question_overlays/`。
- 修復後 2012--2023 detector replay 全部為 45/45，無 missing/duplicate；6 個 affected
  layouts 已重建，post-fix overlays 在 `3.分析結果/output/fixed_question_overlays/`。
- 2017 Q31 仍標記 `incomplete=true`（light OCR 只命中 B anchor），但以明確 Q31→Q32
  sequence evidence 保留，且 bbox 已目視確認不再吞 Q32。
- Existing txt/jsonl 未重跑 VLM；prompt 修復目前只由 regression test 證明指令存在，
  尚未由模型輸出驗證。
- User follow-up found recovered qids were assigned but still outside crops:
  orphan bbox came only from OCR-visible stem/options, so missed printed qids
  shifted `x1` right; tall fraction stems also left page-leading `y1` too low.
  Fixed by same-page stem gutter alignment plus 64 px leading top pad, clamped
  below `甲部`.
- 2022 Q1/Q5 follow-up was a stale-artifact issue: detector replay produced
  x1=197/152 versus stale x1=281/230. A foreground rebuild put both printed
  qids inside their boxes. The refreshed 2021 Q40 overlay is also correct.
- Exact whole-page left-edge equality is unnecessary for these cases: recovered
  questions already reuse the page's detected qid gutter (observed variation
  only 0--3 px). Keep `content_x_max_ratio` right extension because graphs and
  right-side choices can exceed OCR text bounds.

## 2026-07-29 — Instructor integration boundary

- `Qwen25VlClient.generate()` calls Transformers `model.generate()` directly;
  Instructor has no supported patch seam there.
- The safe integration is a parallel, opt-in OpenAI-compatible vision endpoint.
  In shadow mode it adds validated metadata but cannot alter official Stage2
  text, Stage3 sanitize, PageIR, TXT, or TEX.
- `max_retries=1` means one initial request plus at most one validation retry.
  Values above one are rejected locally.

## 2026-07-29 — Python cleanup

- Removed approved one-off diagnostic/smoke/patch scripts and superseded DSE entrypoints.
- Retired the old `draft.jsonl` utilities and deprecated GLM backend.
- Removed no-op `polish_per_page`, unused prompt/client aliases, and the light-OCR stub.
- Kept N-up and the wired optional OCR engines; the locked DSE path is unchanged.
