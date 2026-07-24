# Findings & Decisions

## 2026-07-24 — Ingest contract implementation notes
- OCR crops live at `output/{stem}.figures/<block_id>.png`; stage remaps to job `figures/`.
- New Qdrant writes use `chunk_version=pageir_v2` (old `pageir_v1` points remain readable; use `--reindex` per doc).
- Caption failure skips that figure only; batch continues unless `--fail-fast`.
- Trunk YAML: `skip_figures: false`; experiment branches may keep `true`.

## 2026-07-24 — Wave 2 Ollama install lessons (PC-B)
- Hung `curl | install` left `/usr/local/bin/ollama` without `/usr/local/lib/ollama/llama-server` → generate HTTP 500.
- No passwordless sudo → userspace tarball `https://ollama.com/download/ollama-linux-amd64.tar.zst` → `~/opt/ollama`.
- Ubuntu Server often lacks `python3-venv`; use `uv` for agent venv.
- `qdrant-client` 1.18 removed `Client.search`; use `query_points`.
- Boot criterion: no systemd enable; session `ollama serve` only.

## 2026-07-24 — Trunk + ingest contract (brainstorm → spec)
- Spec: `docs/superpowers/specs/2026-07-24-trunk-qwen-ingest-contract-design.md` (commit `89d8c37`).
- Approach 1: DONE v1 + pageir figure fields + `chunk_version=pageir_v2`; batch from local output/; ColPali backlog.
- Stopped EOD before writing-plans / implementation.

## 2026-07-24 — Publish/ingest/pageir exploration (pre-implementation)
- **DONE v1** already allows nested artifact paths (`figures/...`); validator only requires `{path,sha256}` + `{doc_id}.txt`.
- **Publish/stage gap:** `publish.py` / `job_export.stage_job_artifacts` only copy flat `{doc}.{txt,tex,pageir.json}` — no `figures/` tree.
- **Ingest gap:** `CHUNK_VERSION=pageir_v1`; no `crop_path` payload; embeds `seg.text` only; ignores `crop_relpath`.
- **PageIR gap:** `ContentSegment.crop_relpath` + `SegmentKind.FIGURE` exist in `models.py` but `write_pageir_json` does not emit `crop_relpath`; no OCR path creates figure segments.
- **Figure routing:** `DynamicRouter` skips FIGURE/OTHER (`raw_text=""`, `meta.skipped`); config `skip_figures: true` is unused in Python. `content_crop.py` = page DSE box only, not figure crops for jobs.
- **Batch:** no `batch_export` module yet; per-doc `--publish/--ingest` on `run_ocr_pipeline.py` only.

## 2026-07-24 — Layout bakeoff on `789` content PNG

Same image: `data/pdf_pages/789/page_001.content.png`. Script: `scripts/layout_bakeoff_789.py`. Reports: `output/layout_bakeoff_789/*.json`.

| Engine | layout_s | blocks | Types | Formula routing |
|--------|----------|--------|-------|-----------------|
| **mineru** | **5.059** | 4 | title1 text2 **equation1** | Best: emits `equation` for Q1 frac |
| **doclayout_yolo** | **5.126** | 6 | title1 text3 other2 | Finds formula_caption but mapped → **other** (router skips) |
| **surya** v2 | **220.915** | 5 | title1 text2 other2 | Docker/vLLM **cold start**; Form/other for answer lines; no `equation` type |

**Speed (this host, cold):** MinerU ≈ DocLayout (~5s) ≫ Surya (~221s cold). YOLO log alone ~50ms inference after load.

**Precision (DSE stems / formula boxes):** MinerU > DocLayout ≈ Surya for downstream math routing on this page.

## 2026-07-24 — 789 three-branch scorecard (content crop)
- Content crop applied to **qwen-vl** (question_paper VLM) and **got/mineru** (engine stacks + skip_polish).
- On exam stems, VLM stem prompt dominates; PP-OCR stacks still shatter formulas without that prompt.
- Timings nearly tied (~23–26s); quality ranking independent of speed.

## 2026-07-24 — question_paper extraction
- Goal: DSE exam pages → section header + numbered stems with inline `$...$` only (drop margin warnings / answer lines / footer).
- Path: render → OpenCV/margin content crop → one VLM call/page (`QUESTION_PAPER_PROMPT`); no Surya block route.
- Verified on `dse pp/789.pdf` → `output/789.qp.txt` matches user example (minor spacing).

## 2026-07-23 — Branch scorecard (agent-assisted human fill)
- qwen-vl wins on formula edits / prose min / compile; experiment stacks fail compile under skip_polish.
- mineru UniMERNet formula *bodies* > got plain-text shards when model fires; still not ≤10 min teacher bar on page1.
- Decision: keep **Surya+Qwen** as default feedstock path; optional engines stay experiments until full-doc + polish scorecard.

## 2026-07-23 — OCR GPU MCP gate
- Before every OCR/VLM run: `user-gpu` `list_gpus` / `get_gpu_metrics`.
- Thresholds (free MiB): ≥8k full run; 4–8k prefer `--reuse-layout` or stop surya first; 2–4k Stage2/3 only; <2k do not start.
- Snapshot 2026-07-23 23:56: used **1678** / 12282 MiB (~10.6 GiB free) — clear to run.
- Locked in `.cursor/rules/tool-routing.mdc` Habit 7.

## 2026-07-23 — Agent ownership split
- OCR/TeX agent: feedstock quality + **CLI `--publish`/`--ingest`** (`job_export` stages tagged → `{doc_id}.*`, calls `homelab.ingest`).
- Homelab agent: B host, ufw, key rotation, backups, Wave 2. Does not change OCR engines.
- Env OCR reads: `Z:/`, `QDRANT_URL`, `QDRANT_WRITER_KEY`. Deps: `uv sync --group ingest`.

## 2026-07-23 — OCR publish/ingest bridge
- `output_tag` artifacts (`123.got-ppocr.txt`) are not DONE-named; staging copies to `output/.publish_stage/{doc_id}/`.
- `homelab.ingest` is importable (`pythonpath = ["src", "."]`); scripts still bootstrap repo root on `sys.path`.

## 2026-07-23 — uv migrate (modern-python)
- Source of truth: `pyproject.toml` + `uv.lock`; core deps via `uv add`; groups `dev`/`lint`/`test`/`got`/`ingest`.
- Torch CUDA via pytorch-cu126 index (`2.13.0+cu126`, cuda True after re-pin).
- MinerU **not** in main lock (Py3.14 + transformers 5 + fasttext MSVC) — keep `.venv-mineru312`.
- `surya-ocr` still `uv pip install surya-ocr --no-deps` (not locked; uv sync removes it).
- `uv run pytest`: **120 passed**.

## Homelab Wave 1 (2026-07-23) — closed green
- Root cause of SSH block: A pubkey not in B `authorized_keys` until `install-pc-a-key.sh`.
- Backup script must hit `http://$B_LAN_IP:6333` (not loopback); download snapshots via REST, not `docker cp`.
- Evidence: RP `20260723T152007Z`; points 835; reader upsert/delete 403; ufw ENABLED; Wave 2 deferred.

## Legacy extract path (historical — from UPGRADE_NOTES.md)
- Older flow: `extract_questions.py` → `data/draft.jsonl` → `jsonl_to_latex.py` (GLM-era notes).
- Prefer `run_ocr_pipeline.py` / content-first for marking schemes.
- Known legacy pitfalls (still relevant): Chinese path → open via PIL not `file://`; YAML `256*28*28` must be int; short (a)(b) merge via prompts / `merge_draft_subparts.py`.
- AIbuliding LoRA training remains a separate consumer of promoted drafts — do not auto-promote OCR output.

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
