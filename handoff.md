# Handoff — P-ocr (read this first)

**Date:** 2026-07-23 (architecture rewrite: P-ocr / Approach B)  
**Repo:** `C:\Users\a1217\OneDrive\桌面\aiworkplace\pdf scaner`  
**Git:** branch `main` @ `02a68a6` (plus large uncommitted work)  
**Audience:** next Cursor agent — open this, then `task_plan.md` / `findings.md` / `progress.md`, then act.

Do **not** invent state. Prefer filesystem planning docs over chat memory. Never paste API keys (Qdrant reader key in `~/.cursor/mcp.json`; writer keys in B `~/homelab/.env` only).

**Naming:** the product is **P-ocr** (formerly 北辰). Do not call it an “OCR product.” OCR is only the raw-material pipeline.

---

## 1. Goal — P-ocr

**P-ocr** = 題庫 → AI 老師 Chat.  
OCR is only how we produce raw materials (`.tex` / `.txt` / `.pageir.json`). Teacher edit bar for those drafts: ≤10 minutes, then reuse.

- Chat / 老師 UI are **not** the current milestone.
- Near-term (≥2 months): build a data plane that will not be thrown away.
- Do **not** rebuild DeepTutor.
- SearXNG / CI / Grafana = backlog.

**OCR draft bar (content-first):** complete formulas + readable **linear** text ≫ 解|分|備註 tabular layout. Layout fidelity is not a Ship 1 pass/fail.

**Python:** always `.\.venv\Scripts\python.exe` with `PYTHONPATH=src` (or pytest from venv).

---

## 2. Research / deploy topology (Approach B — APPROVED)

Design authority: `~/.gstack/projects/pdf-scaner/a1217-main-design-20260722-210437.md`

```
PC-C (辦公室筆電)
  └─ RustDesk → PC-A (家裡 Win + Cursor)
                   ├─ OCR / VLM /（將來）老師 LLM
                   ├─ ingest CLI（Qdrant **唯一 writer**）
                   └─ LAN → PC-B (Ubuntu 資料真相)
                              ├─ Qdrant :6333
                              ├─ Samba `/data/pdf-scaner` → A 上常映射 `Z:`
                              └─（Wave 2+）輕量 agent 唯讀；Ollama 預設 OFF
```

| 機 | 硬體 | OS | 角色 |
|----|------|-----|------|
| A | 9600X + 4070 Super 12GB + 32GB | Windows | OCR/VLM、Cursor、ingest 寫入、將來老師 LLM |
| B | 5600X + 1660S + 32GB | Ubuntu 24.04 on SATA（Windows 留 M.2） | Qdrant + jobs 檔案真相；`homeserver` / `keith` |
| C | 筆電 | — | 只遙控 A；不跑 Cursor／不當 Qdrant 主客戶端 |

- A↔B: same-switch LAN (`192.168.1.107`); Tailscale for remote SSH (`keith@100.101.145.120`).
- **1660S is not the teacher model.**

### Data ownership (locked)

| 資料 | 權威 | 誰可寫 |
|------|------|--------|
| OCR 工作中產物 | A 本地 | OCR pipeline |
| 已完成 job | B `/data/pdf-scaner/jobs/<job_id>/` | A 經 publish 原子發布後，**B 為權威** |
| Qdrant vectors | B | **僅** A 上 ingest CLI（writer key） |
| MCP / Chat / B agent | — | **reader only** |

**Atomic publish:** `.incoming/<job_id>/`（無 DONE）→ 校驗 sha256 → 寫 `DONE.json` → `mv` 到 `jobs/<job_id>/` → ingest **只掃** `jobs/`.  
Contract: `2_生產線/_handbooks/homelab/DATA_PLANE.md` + design `DONE.json` schema.

---

## 3. Current status (OCR feedstock + data plane)

### OCR engine comparison

- Spec: `2_生產線/_history/specs/2026-07-23-ocr-engine-adapters-design.md`
- Plan: `2_生產線/_history/plans/2026-07-23-ocr-engine-adapters.md`
- Scorecard: `3.分析結果/_reports/p-ocr-branch-scorecard.md`
- Branches: `qwen-vl`, `got-ppocr`, `mineru-ppocr`

### Green

| Area | Evidence |
|------|----------|
| Ship 1 content-first | Committed `dbd2e02` — PageIR / segmenter / formula_integrity / always per-page polish |
| Ship 1.5 `--check-compile` | Committed `365c186` — `compile_check.py` + CLI flags |
| Greedy + `layout.release` (code) | Greedy decode + docker stop `surya-vllm-*`; limit-1 golden exit 0 (2026-07-22) |
| Compile path (offline) | Re-finalize `output/123.tex` → **COMPILE_OK**, PDF ~101KB (2026-07-23). Backup: `output/123.tex.bak_tabular` |
| Segmenter / TABLE_ROUTER defenses | Tabular/CJK/`$$`/`\caption` strip; linear TABLE_ROUTER (no Markdown/tabular) |
| Unit tests (compile-fix arc) | 23 passed on segmenter / content_first* / formula_integrity |
| Homelab Wave 0 | Qdrant `http://192.168.1.107:6333`, Samba, MCP reader — **done** |
| Homelab Wave 1 smoke | Job `20260723-005247-123` → `exam_segments_v1` **827 points**; idempotent re-ingest still 827 |

### Broken / watch / uncommitted

| Issue | Notes |
|-------|--------|
| Uncommitted critical (important) | Greedy / `layout.release` / TABLE_ROUTER·segmenter defenses / related tests / `config` temperature 0 — **not committed** |
| Full OCR historically failed compile | 14p golden 2026-07-22 exit 12 (tabular-in-math); offline repair green; optional full re-run with new TABLE_ROUTER not done |
| Qdrant writer key in terminal history | Rotate when convenient (do not commit keys) |

### Uncommitted paths (verify with `git status` / diffs)

- `src/ocr_pipeline/vlm_client.py` — Qwen greedy `build_generation_kwargs`
- `src/ocr_pipeline/layout.py` — `_stop_surya_docker_vlms` + GPU headroom wait in `release()`
- `src/ocr_pipeline/segmenter.py`, `prompts.py` (TABLE_ROUTER linear), `formula_integrity.py`, content-first related
- `config/ocr_pipeline.yaml` — `temperature: 0.0`
- Tests: `tests/test_vlm_greedy_decode.py`, `tests/test_layout_release.py`, segmenter/content_first/integrity updates
- Planning: `task_plan.md`, `findings.md`, `progress.md`
- Homelab: `homelab/` (compose, ingest, DONE schema, docs)
- Misc: `.cursor/rules/*`, `golden_run_cf_report.txt`, etc.

**Always-on:** `.cursor/rules/planning-with-files.mdc` — update `task_plan.md` / `findings.md` / `progress.md` (2-action rule).

**Optional next (not blocking):** full OCR re-run with new TABLE_ROUTER (confirm Stage2 also linear); Phase 2.8 speed; LayoutArtifact resume.

---

## 4. Immediate next actions (ordered)

User may choose; default order from `task_plan.md` / `progress.md`:

### 1) Commit compile fix + VRAM/greedy package (ask user first)

Only commit when the user explicitly asks. Suggested scope:

- Greedy decode + layout docker release + their tests
- Segmenter / TABLE_ROUTER / integrity / content-first compile defenses + related tests
- Config temperature 0
- Planning docs if user wants them in the same commit

```powershell
cd "C:\Users\a1217\OneDrive\桌面\aiworkplace\pdf scaner"
git status -sb
git diff --stat
# after user approval: stage relevant paths, commit (no secrets, no .env)
```

### 2) Phase 2.8 speed

- Lower Stage2/3 `max_new_tokens` in config / client defaults
- LayoutArtifact resume (Phase 2.5b) — persist LayoutBlock JSON; resume route/polish without re-Surya
- Never dual-run `run_ocr_pipeline` on 12GB

### 3) Optional full OCR re-run with new TABLE_ROUTER

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe run_ocr_pipeline.py data\sources\123.pdf --check-compile
# Expect: [Layout] Stopped docker VLM: surya-vllm-… before Stage2; exit 0 if compile OK
# Monitor GPU; avoid second concurrent pipeline PID
```

### 4) Homelab follow-ups (Wave 1 already green)

- Optional: second doc publish/ingest; search query smoke via `user-qdrant` / `qdrant-find`
- Rotate exposed writer key on B
- Do **not** add Chroma/Cognee/Mengram for 題庫/記憶 — Qdrant on B is the store (dual-truth ban)

### Between tasks

- Append dated notes to `progress.md`; mark phases in `task_plan.md`
- Log errors in `task_plan.md` Errors table (never silently retry same failure)

---

## 5. Architecture — OCR pipeline (feedstock on A)

Product bar: complete formulas + readable linear text ≫ 解|分|備註 tables.

```
PDF → page images
  → Layout (Surya v2 / Docker vLLM)
  → layout.release()  # MUST docker stop surya-vllm-* + wait GPU headroom
  → Stage2 routers（VLM greedy only）
  → Stage3 永遠 per-page polish（禁止只靠 full-doc polish）
  → content_first.finalize → .tex + .txt + .pageir.json
  → 可選 --check-compile
```

**Locked VLM:** Qwen2.5-VL-7B **4bit**; `temperature=0` / `do_sample=False` (else CUDA multinomial assert).

### Key files

| Path | Role |
|------|------|
| `run_ocr_pipeline.py` | CLI entry |
| `config/ocr_pipeline.yaml` | VLM/layout knobs (`temperature: 0.0`) |
| `src/ocr_pipeline/layout.py` | Surya + **`release()` docker stop** |
| `src/ocr_pipeline/vlm_client.py` | Qwen client; **`build_generation_kwargs` greedy** |
| `src/ocr_pipeline/routers.py` | Stage2 routing |
| `src/ocr_pipeline/prompts.py` | **`TABLE_ROUTER_PROMPT` = linear** (no tabular/Markdown tables) |
| `src/ocr_pipeline/segmenter.py` | Stitch → PageIR; tabular/CJK/`\caption` defenses |
| `src/ocr_pipeline/formula_integrity.py` | Math body checks; flags tabular chrome in math |
| `src/ocr_pipeline/content_first.py` | `finalize_content_first` → txt/tex/pageir |
| `src/ocr_pipeline/compile_check.py` | Ship 1.5 compile gate |
| `homelab/` | B data plane + `ingest/` publish/DONE |
| `output/123.*` | Current golden artifacts; `.tex.bak_tabular` pre-repair backup |

### Design docs (outside repo)

- Content-first: `~/.gstack/projects/pdf-scaner/a1217-main-design-20260721-153800.md`
- Eng plan: `~/.gstack/projects/pdf-scaner/a1217-main-eng-review-plan-20260721-content-first.md`
- Dual-PC / Approach B: `~/.gstack/projects/pdf-scaner/a1217-main-design-20260722-210437.md` (**APPROVED**)

---

## 6. Homelab (Wave 0–1)

| Wave | Status |
|------|--------|
| Wave 0 | **Done** — Qdrant `http://192.168.1.107:6333`, Samba, MCP reader |
| Wave 1 smoke | **Green** — job `20260723-005247-123` → collection `exam_segments_v1` **827 points**; idempotent re-ingest still 827 |

| Item | Value |
|------|--------|
| B LAN | `192.168.1.107` |
| B Tailscale SSH | `ssh keith@100.101.145.120` |
| Qdrant | `http://192.168.1.107:6333` (`/readyz`) |
| Samba on A | `Z:\` → `\\192.168.1.107\pdf-scaner` (B `/data/pdf-scaner`) |
| Jobs example | `Z:\jobs\20260723-005247-123` |
| Ingest code | `homelab/ingest/` (`done.py`, `publish.py`, `ingest.py`) |
| Contract | `2_生產線/_handbooks/homelab/DATA_PLANE.md`, `2_生產線/_handbooks/homelab/README.md` |
| Embedding | On **A**: `nomic-ai/nomic-embed-text-v1.5` (768-d) |
| Collections | MCP `memories` ≠ 題庫 collection (`exam_segments_v1`) |

Keys: reader in `~/.cursor/mcp.json`; writer/reader pair on B `~/homelab/.env`. **Never commit or paste values.**

**Ban:** do not add Chroma / Cognee / Mengram for 題庫/記憶 (dual truth).

---

## 7. Pitfalls (do not rediscover)

1. **P-ocr ≠ OCR** — OCR is feedstock only; do not scope Chat UI or “OCR product” as the north star.
2. **CUDA multinomial / `TensorCompare.cu` assert** — any `temperature>0` → `do_sample=True` → crash on 4bit Qwen-VL. Keep greedy.
3. **Surya VRAM leak** — `VllmBackend.stop()` is handle-only; atexit docker cleanup is too late for Stage3. Must `docker stop surya-vllm-*` in `release()` and wait for free VRAM (~11GB → ~390MB after fix).
4. **Tabular-in-math** — Stage2/polish can emit `\begin{tabular}` / `\hline` / `&` rows; if classified as math → `Missing $` / `Misplaced \noalign`. Segmenter must explode chrome; `_TEX_MATH_HINT` must **not** match bare `\begin`.
5. **Always per-page polish** — never rely on full-doc-only polish (empty PageResult → Markdown leak).
6. **No dual OCR pipeline on 12GB** — two `run_ocr_pipeline` PIDs → OOM / fights.
7. **Data ownership** — never bypass atomic publish/`DONE.json` by writing straight into `Z:\jobs`; ingest only scans completed `jobs/`.
8. **Writer uniqueness** — only A ingest CLI writes Qdrant; MCP / Chat / B agent = reader only.
9. **No second vector DB** for 題庫/記憶 (no Chroma/Cognee/Mengram).
10. **1660S ≠ teacher LLM** — B is data truth + optional light agent later.
11. **OneDrive phantom diffs** — prefer content diffs; do not commit noise blindly.
12. **Secrets** — never commit `.env`, Qdrant keys, or paste key values into chat/docs.

---

## 8. Cursor toolchain (A — R&D aid, not product core)

Rules: `planning-with-files`, `mcp-routing` (`.cursor/rules/`).

### Skills — when to invoke

Archived routing reference: `2_生產線/_archive/CLAUDE.md`.

| Skill / rule | When |
|--------------|------|
| **planning-with-files** | Every non-trivial task — `task_plan.md` / `findings.md` / `progress.md` |
| `/investigate` | Bugs, CUDA/OOM, compile errors, flaky OCR |
| `/review` | Pre-landing diff review |
| `/qa` / `/qa-only` | Behavior QA of pipeline / CLI outputs |
| `/ship` / `/land-and-deploy` | PR / ship / land |
| `/spec` | Backlog-ready issue/spec |
| `/office-hours` | Product ideas / brainstorming (P-ocr scope) |
| `/plan-eng-review` | Architecture / eng plan |
| `/plan-ceo-review` | Strategy / scope |
| `/autoplan` | Full review pipeline |
| `/context-save` / `/context-restore` | Session continuity |
| `/careful` / `/guard` / `/health` | Safety / health |
| `systematic-debugging` | Hard bugs; structured repro |
| `pytest-skill` | Writing/running pytest |
| `modern-python` | Python style / packaging hygiene |
| `pdf` | PDF-specific help |
| `mcp-builder` | New MCP (rare; do not add conflicting vector MCPs) |
| `insecure-defaults` / `varlock` | Secrets / insecure defaults review |
| `qdrant-*` suite | Homelab Qdrant deployment / search quality |

New Cursor skills under `~/.cursor/skills`: `pdf`, `mcp-builder`, `modern-python`, `insecure-defaults`, `varlock`, `systematic-debugging`, `pytest-skill`.

### MCP servers — when to use + status

**Rule:** Call `GetMcpTools` for a server **before** `CallMcpTool`. Prefer domain MCP over Shell/web guessing.

Configured in `~/.cursor/mcp.json` (session ids often prefixed `user-`):

| Server | When to use | Notes |
|--------|-------------|-------|
| `user-qdrant` (`qdrant-find`) | Semantic search memories / exam segments on B | **READ ONLY**; reader key in mcp.json (never paste); `memories` ≠ `exam_segments_v1` |
| `user-zero-api-key-web-search` | Live web search / claim check / browse | Prefer over guessing |
| `user-codebase-memory` | Repo graph, call chains, architecture | Index once if needed |
| `user-github` | Issues/PRs/code search | Needs `GITHUB_PERSONAL_ACCESS_TOKEN` |
| `user-filesystem` | Repo / aiworkplace / `Z:\` | Do not bypass DONE.json |
| `user-context7` | Library/API docs | Prefer over guessing; `CONTEXT7_API_KEY` via header in mcp.json (never paste) |
| `user-gpu` | VRAM / util before OCR | Prefer before long runs |
| `user-arxiv-latex` | arXiv LaTeX / sections | Prefer over HTML scrape |
| `user-zotero` | Personal library / citations | Needs local Zotero + API |
| `cursor-app-control` | Move root, open resources | Built-in |
| `plugin-vercel-vercel` | Vercel | **Do not use unless user asks** |

Status snapshot (2026-07-23): listed servers were `ready`. Re-check via `GetMcpTools` if a tool fails.

**Soft triggers:** 查文件→context7; 搜網→zero-search; 誰在叫/架構→codebase-memory; PR/issue→github; VRAM→gpu; arXiv→arxiv-latex; Zotero→zotero; 題庫/memories→qdrant.

---

## 9. Verification commands

```powershell
cd "C:\Users\a1217\OneDrive\桌面\aiworkplace\pdf scaner"
$env:PYTHONPATH = "src"

# Unit subset (VRAM / greedy / compile-defense)
.\.venv\Scripts\python.exe -m pytest tests/test_vlm_greedy_decode.py tests/test_layout_release.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_segmenter.py tests/test_content_first.py tests/test_content_first_prompts.py tests/test_formula_integrity.py -q

# DONE schema (homelab)
.\.venv\Scripts\python.exe -m pytest tests/test_done_schema.py -q

# Compile gate on existing draft (offline)
.\.venv\Scripts\python.exe -c "from pathlib import Path; from ocr_pipeline.compile_check import compile_tex; r=compile_tex(Path('output/123.tex')); print(r.ok, r.message, r.pdf_path)"

# Limit-1 golden (needs GPU free; Surya docker will start then stop)
.\.venv\Scripts\python.exe run_ocr_pipeline.py data\sources\123.pdf --limit 1 --reuse-images --check-compile

# GPU
nvidia-smi
# or MCP: user-gpu → get_gpu_metrics / gpu_summary
```

Expect after layout release: log line like `[Layout] Stopped docker VLM: surya-vllm-…` and free VRAM recovering before Stage2/3.

---

## 10. Do NOT / out of scope (Wave 0–1)

**Explicit non-goals now:**

- AI 老師 UI / Chat product surface
- Second vector store for 題庫/記憶 (Chroma / Cognee / Mengram)
- B as teacher LLM (1660S)
- Writing `Z:\jobs` while bypassing `DONE.json` / atomic publish

**Also do not:**

- Call P-ocr an “OCR product”
- Re-enable sampling / non-zero temperature for VLM generate
- Skip `docker stop surya-vllm-*` in layout release
- Restore marking-scheme tabular as Ship 1 success metric
- Dual-run OCR pipeline on this GPU
- Paste secret keys into git, `handoff.md`, or chat
- Use Vercel MCP unless user asks
- Elevate MinerU until formula *bodies* still dominate edit time (Phase 4)
- Start Wave 2 Chat/SearXNG/Ollama on B without user ask
- Rebuild DeepTutor; treat SearXNG / CI / Grafana as current work
- Rely on TodoWrite alone — persist in planning files

Ship 2 OCR overlay PDF and LayoutArtifact resume are backlog, not “broken production.”

---

## Quick resume checklist

1. Read this file + `task_plan.md` (Current Phase / Next Action) — product = **P-ocr**
2. `git status -sb` and confirm uncommitted critical paths
3. Ask user which priority: **commit** vs **2.8 speed** vs **full OCR re-run** vs **homelab**
4. Respect data ownership table (A ingest = only Qdrant writer)
5. Use planning-with-files + MCP routing; prefer `user-gpu` before long OCR
