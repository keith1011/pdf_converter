# Findings & Decisions

## 2026-07-26 — OCR quality gate implemented (TDD)
- Issues #4 (core) + #3 (wiring); Copilot assign **failed** (`Bot does not have access`) → local TDD
- Module `ocr_pipeline.quality`; ingest/batch flags; finalize emits `.quality.json`
- Focused tests 29+ green; ruff clean on touched files; ohm `analyze_codebase` on quality: 0 issues
- Offline `nup-v2`: fail (le3=0.277, ge20=0.225, admitted_est=0.533)

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
- Full OCR exit 0 (~843s): `output/2014-DSE-MATH-CP-2.nup-full.*`
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
- Spec: `docs/superpowers/specs/2026-07-25-nup-classifier-crop-design.md`
- Plan: `docs/superpowers/plans/2026-07-25-nup-classifier-crop.md`
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
4. Tests: `tests/test_mcq_coalesce.py` (+ segmenter/content_first) **27 passed**.

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
- Focused tests: 2 passed (`tests/test_ingest_figures.py`).

## 2026-07-24 — Task 4: staging and figure publication
- `publish()` currently flattens every artifact to `src.name`, so nested figure paths cannot be preserved.
- `validate_done_dict()` accepts nested artifact paths but only enforces on-disk listing for optional top-level PageIR/TeX files; `figures/*.png` needs the same completeness check.
- `src/ocr_pipeline/job_stage.py` and figure publish tests do not yet exist.

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
- No `QDRANT_WRITER_KEY` / `WAVE1_SSH_PASSWORD` in User/Process env on A — ingest + reader neg-test wait on keys in `%USERPROFILE%\.homelab\qdrant.a.env` (generated) + B `apply-qdrant-env.sh`.
- A-side RP pack works without SSH: `RP_ID=20260723T122750Z`, `DONE_count=1` in `jobs.tar.gz`.
- Second job published: `Z:\jobs\20260723-130314-wave1demo` (`doc_id=wave1demo`, 8 segments) — ingest pending key rotation.
- Follow-along path: `homelab/scripts/RUN_ON_B.md` + `wave1-on-b.sh`.

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
- **Symptom:** `| --- |`, `<br>` in `output/123.txt`
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
- **Fix (2026-07-23):** segmenter strips `table`/`tabular`/`hline` + `&` rows; `_TEX_MATH_HINT` no longer matches bare `\begin` / bare `\`; `TABLE_ROUTER_PROMPT` → linear (no Markdown/tabular); integrity flags tabular chrome in math; CJK peeled out of `$...$`; junk `\frac{CJK}{-}` / `\caption` dropped. **Offline re-finalize of `output/123.tex` → `--check-compile` OK (PDF ~101KB).**

## Commits
| SHA | What |
|-----|------|
| `dbd2e02` | Content-first Ship 1 |
| `365c186` | Ship 1.5 `--check-compile` |
| `e6bcca7` | Greedy decode + Surya docker release + tabular compile defenses |
| *(pending)* | Phase 2.8 speed: tokens + LayoutArtifact + single-instance lock |

## Phase 2.8 speed (2026-07-23)

Evidence: full golden `output/123.tex` ~15KB; Stage1 often 2–3 blocks/page — 4096 tokens wasted decode budget.

| Change | Detail |
|--------|--------|
| Token budgets | `max_new_tokens: 2048` (Stage3 polish default); `max_new_tokens_route: 1024` (Stage2 crops) |
| API | `VlmClient.generate(..., max_new_tokens=)` override; routers pass route budget |
| LayoutArtifact | `data/pdf_pages/<stem>/layout.json` written after Surya; `--reuse-layout` skips Surya |
| Dual-run guard | `output/.ocr_pipeline.lock` + live PID; `--allow-concurrent` to override |

If Stage3 starts warning `polish truncated`, raise `vlm.max_new_tokens` before touching route budget.

## Uncommitted (as of 2026-07-23 Phase 2.8)
- Phase 2.8 code + tests + planning docs (not committed yet)
- `homelab/`, `.cursor/`, phantom OneDrive M files, pytest/golden artifacts

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
3. **Light ruff** — `pyproject.toml` + `requirements-dev.txt`; install with `uv pip install -p .venv ruff` (GPU requirements.txt kept); `ruff check src/ocr_pipeline run_ocr_pipeline.py arrange_only.py tests` clean
