# Task Plan: PDF Scaner — content-first OCR → 可編輯 TeX → 可選編譯

## Goal
PDF → content-first 草稿（`.tex` + `.txt` + `.pageir.json`）→ 可選 `--check-compile` PDF；教師 ≤10 分鐘手改後可 reuse。

## Current Phase
**Ingest contract (figure + batch) — implemented 2026-07-24** — Slice A/B/C landed (pageir_v2, figures/, batch_export). Next: optional GPU smoke with VRAM gate; ColPali still backlog.

## Agent ownership (locked 2026-07-23)

| Lane | Owns | Does **not** own |
|------|------|------------------|
| **OCR / TeX** | `src/ocr_pipeline/`, engines, scorecard, `.tex`/`.txt`/`.pageir.json`, compile-check, GPU OCR, **CLI `--publish`/`--ingest`** via `job_export` | B SSH/ufw, Qdrant key rotation, Wave 2, compose on B |
| **Homelab / data plane** | B host, `DATA_PLANE.md`, ufw, Samba, backups, keys, Wave 1 ops | OCR engine quality, TeX draft bar, VLM decode |

OCR consumes Wave 1 env (`Z:/`, `QDRANT_URL` / `QDRANT_WRITER_KEY`). Do not dual-run OCR on 12GB.

## Routing (locked)
- Always: planning-with-files (`task_plan.md` / `findings.md` / `progress.md`)
- Domain table: `.cursor/rules/tool-routing.mdc` (Skill + MCP); handbooks `docs/SKILL_HANDBOOK.md`, `docs/MCP_HANDBOOK.md`

## Hardware / model

| Item | Decision |
|------|----------|
| GPU | RTX 4070 Super **12GB** |
| VRAM gate | Before every OCR run: MCP **gpu** `list_gpus`; adjust per `.cursor/rules/tool-routing.mdc` Habit 7 |
| Python | **3.12** (`.python-version`; main `.venv` via uv). Do not use 3.14 for this repo. |
| Default VLM | **Qwen2.5-VL-7B-Instruct 4bit** |
| **Trunk stack** | **MinerU layout + Qwen text + Qwen formula** (locked 2026-07-24) |
| Formula knives | got / unimernet opt-in only |
| Decode | **greedy only** (`do_sample=False`) — sampling → CUDA multinomial assert |
| Token budgets | Stage3 polish **2048**; Stage2 route **1024** (`max_new_tokens_route`) |
| Surya v2 | Optional fallback；Docker cold ~221s — not trunk |
| MinerU runtime | Prefer `.venv-mineru312` until mineru is in main uv group |
| Order | Layout (MinerU) → Stage2/3 Qwen → content-first finalize → optional compile |

## Phases

### Phase 1–2.5a: 環境 / sanitize / VlmClient / CLI DX — complete

### Phase 2.5c: Content-first Ship 1 — complete
- [x] PageIR / segmenter / formula_integrity / content_first
- [x] Always per-page polish → PageResult
- [x] Segmenter strips Markdown / `<br>` / align|itemize chrome
- [x] Commit `dbd2e02`

### Phase 2.5d: Ship 1.5 `--check-compile` — complete
- [x] `compile_check.py` + CLI flags on `run_ocr_pipeline` / `arrange_only`
- [x] Commit `365c186`

### Phase 2.6: Runtime stability (greedy + Surya VRAM) — complete
- [x] Force greedy decode (`build_generation_kwargs`) + `temperature: 0.0`
- [x] `layout.release()` stops Surya manager **and** `surya-vllm-*` containers + wait GPU headroom
- [x] limit-1 golden + `--check-compile` → exit 0, PDF written (2026-07-22)
- [x] Commit greedy + layout release fixes (2026-07-23)
- **Status:** complete

### Phase 2.7: Full-doc golden (14 pages) — compile green (offline re-finalize)
- [x] `123.pdf` full OCR run with content-first
- [x] Tabular/CJK/`$$`/`\caption` segmenter defenses
- [x] Offline re-finalize from `.tex.bak_tabular` → `--check-compile` **OK** (2026-07-23)
- [ ] Optional: full OCR re-run with new TABLE_ROUTER (confirm Stage2 also linear)
- **Status:** compile path green on repaired drafts

### Phase 2.8: Runtime speed — complete (code; commit pending)
- [x] Lower Stage2/3 `max_new_tokens` (polish 2048 / route 1024) + `generate(..., max_new_tokens=)`
- [x] LayoutArtifact persist/resume (`layout.json` + `--reuse-layout`) — folds Phase 2.5b
- [x] Single-instance lock (`output/.ocr_pipeline.lock`; `--allow-concurrent` escape)
- [ ] Commit Phase 2.8 package when user asks
- **Status:** functionally complete; uncommitted

### Task 4: Engine factory/router/pipeline wiring — complete
- [x] Wire Surya/VLM adapters through factory and routers
- [x] Add skip-polish, output tagging, and stage timing
- [x] Run focused regression suite (20 passed)

### Task 6: PP-OCR Traditional Chinese text engine — in progress
- [x] Add lazy `PpocrTextEngine` and PP-OCR requirements file
- [x] Wire `engines.text: ppocr` while retaining the VLM default
- [x] Add mocked adapter and factory tests
- [ ] Run required focused test command and commit (blocked: terminal returned no exit status)

### Task 7: GOT + DocLayout-YOLO experiment — complete with concerns
- [x] Add lazy, fail-loud DocLayout-YOLO `LayoutEngine` and GOT `FormulaEngine`
- [x] Wire `doclayout_yolo` / `got` factory selections; reuse PP-OCR
- [x] Add CPU-only mocked tests (7 passed)
- [x] Create `got-ppocr` branch configuration and commit
  - [ ] GPU smoke skipped: DocLayout-YOLO and PaddleOCR are not installed
  - [x] GPU smoke limit-1 (2026-07-23): total=33.880s → `output/123.got-ppocr.tex` (PP-OCR CPU; GOT HF-native)

### Task 8: MinerU + UniMERNet experiment — complete with concerns
- [x] Add lazy, fail-loud MinerU `LayoutEngine` and UniMERNet `FormulaEngine`
- [x] Wire `mineru` / `unimernet` factory selections; retain Surya/VLM defaults
- [x] Add CPU-only mocked adapter and factory tests
- [x] Commit source package on `main` (`87801bf`)
- [x] Create and commit `mineru-ppocr` config branch (`85a8576`), then return to `main`
- [x] Focused CPU pytest: 10 passed
  - [ ] GPU smoke skipped because no cached optional models
  - [x] GPU smoke limit-1 (2026-07-23): total=39.228s → `output/123.mineru-ppocr.tex` (dedicated `.venv-mineru312`, transformers 4.57)

### Task 10: P-ocr branch comparison scorecard — complete
- [x] Scorecard: `docs/superpowers/evals/p-ocr-branch-scorecard.md`
- [x] References: spec `docs/superpowers/specs/2026-07-23-ocr-engine-adapters-design.md`; plan `docs/superpowers/plans/2026-07-23-ocr-engine-adapters.md`
- [x] Comparison branches: `qwen-vl`, `got-ppocr`, `mineru-ppocr`; score formula edits, prose editing time, and compile only (timings logged only)

| Error | Resolution |
|-------|------------|
| Initial focused pytest invocation returned no terminal exit status. | Re-run after implementation and record the explicit result. |
| Task 6 focused pytest invocation returned no terminal exit status twice. | `cmd.exe` fallback also returned no status; report the terminal limitation and leave test/commit verification to the parent. |
| Task 7 requested pytest glob was not expanded by PowerShell/pytest. | Ran the four explicit matching test files; 7 passed. |
| Task 7 GPU smoke dependencies are absent (`doclayout_yolo=False`, `paddleocr=False`). | Skip model download/install to avoid multi-GB unbounded work; mark DONE_WITH_CONCERNS. |
| PowerShell rejected the Bash-style `&&` in a diff validation command. | Ran the validation command separately using PowerShell-compatible execution. |
| The Windows WSL `bash` shim has no `/bin/bash`, so the required Bash heredoc commit form cannot run. | Use PowerShell's native multiline string to pass the same one-line commit message. |
| Task 8 focused pytest invocation returned no shell exit status. | Record the terminal limitation; do not claim the CPU suite passed without an explicit result. |
| Task 10 status/diff/log shell checks returned no exit status. | Record the limitation; inspect edited files directly and retry only the scoped staging/commit command. |

### Phase 2.5b: LayoutArtifact resume — complete (via 2.8)
- [x] Persist LayoutBlock JSON; resume route/polish without re-Surya
- **Status:** complete (see Phase 2.8)

### Phase Ship 2: OCR overlay PDF — pending
- [ ] `output/<stem>.ocr_overlay.pdf` — page image + OCR text tied to segment bbox / source_block_id
- Priority P2; after feedstock quality is good enough

### Backlog (from former TODOS.md)
- [x] `--check-compile` Ship 1.5 — done
- [x] VlmClient + Qwen 4bit default — done
- [x] LayoutArtifact `--reuse-layout` — done (Phase 2.8)
- [x] Tabular marking-scheme Ship 1 bar — **SUPERSEDED** by content-first
- [ ] Optional: real MinerU/UniMERNet as default math path only if formula *bodies* still dominate edit time (adapters already exist; scorecard first)
- [ ] CLI consolidation (`python -m ocr_pipeline …`) — deferred (root entry scripts stay for now)

### Phase H0: Homelab Wave 0 (PC-B data plane) — complete
- [x] Design APPROVED (`a1217-main-design-20260722-210437.md`)
- [x] OS: Ubuntu 24.04 on SATA (`homeserver` / `keith`); Windows kept on M.2
- [x] Repo scaffold: `homelab/`
- [x] Docker + Qdrant; from A: `curl http://192.168.1.107:6333/readyz`
- [x] Tailscale SSH: `keith@100.101.145.120`
- [x] Samba `\\192.168.1.107\pdf-scaner` mapped on A
- [x] Cursor MCP → B (`QDRANT_URL` + reader key + read-only); collections empty (fresh)
- **Status:** Wave 0 complete

### Phase H1: Homelab Wave 1 (Linux data plane finish) — complete
- [x] Repo scripts: `homelab/scripts/` (ufw, backup RP, restore drill, key apply, reader neg-test, wave1-on-b)
- [x] `DATA_PLANE.md` firewall/backup/key checklist → **Wave 1 green**
- [x] RP `20260723T152007Z` (jobs + full/collection Qdrant snapshots) + restore-drill PASS
- [x] A→B SSH key auth (`id_ed25519_homeserver`)
- [x] B `ufw` enabled (`UFW_DONE`); Qdrant/Samba scoped to A LAN
- [x] Keys rotated; A MCP reader + User env writer; reader neg-test PASS (403)
- [x] Docs: `123` (827) + `wave1demo` (8) = **835** points; re-ingest idempotent
- [x] Wave 2 stays **closed** until user opens it
- **Status:** complete (2026-07-23)

### Phase H2: Homelab Wave 2 (B Ollama + read-only agent) — complete
- Gate (all green before start): Wave 1 + restore drill + ≥2 docs + reader neg-test — **PASS**
- [x] Ollama on B (userspace `~/opt/ollama`); `llama3.2:1b` + `nomic-embed-text`; CUDA on 1660S; **not** on boot
- [x] B query agent: Qdrant **reader** + filesystem allowlist **read-only** (`jobs/` DONE trees)
- [x] Smoke: agent hits `wave1demo`; reader upsert → 403; `WAVE2_B_DONE` written
- [x] `DATA_PLANE.md` Wave 2 section; compose stays Qdrant-only (no boot Ollama)
- **Out of scope (still closed):** teacher Chat UI, SearXNG, Grafana, 7B+ on B, MCP gateway
- **Status:** complete (2026-07-24)

### Phase 3: Qdrant ingest — after H0 green (was optional-parallel)

### Phase 4: MinerU — only if formula *bodies* still dominate edit time

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Content-first > layout fidelity | Teacher bar = complete formulas/text, linear OK |
| Ship 1 = tex+txt+pageir; PDF = Ship 1.5 | Eng-review 15B |
| Always per-page polish | Full-doc polish left PageResult empty → Markdown leak |
| Greedy VLM only | `temperature>0` → `torch.multinomial` CUDA assert on 4bit Qwen-VL |
| Explicit docker stop in release | Surya `VllmBackend.stop()` is handle-only; atexit too late for Stage3 |
| planning-with-files always on | User 2026-07-22; project rule `.cursor/rules/planning-with-files.mdc` |
| Dual-PC Approach B data plane | ≥2mo foundation; Qdrant/jobs on B; Cursor on A via RustDesk |
| **B OS = Ubuntu Server 24.04 LTS**（退路 Debian 12） | Best docs; Debian if Ubuntu storage probing crashes |
| Stage3 tokens 2048 / Stage2 route 1024 | Full `123.tex` ~15KB; crops rarely need 4k; raise if polish truncates |
| LayoutArtifact beside page PNGs | `data/pdf_pages/<stem>/layout.json`; `--reuse-layout` skips Surya |
| Single-instance OCR lock | Dual `run_ocr_pipeline` OOMs on 12GB; lockfile + live-PID check |
| **Trunk = Qwen2.5-VL** (2026-07-24) | Scorecard + bakeoff; got/unimernet = formula knives only |
| **Trunk layout = MinerU** (2026-07-24) | Better equation boxes than DocLayout/Surya; ~5s hot; use `.venv-mineru312` for OCR |
| Ingest = text + figure crop+caption | Embed caption; crop on job; DONE schema 1; `pageir_v2` |
| Batch publish from `output/` | Multi doc_id sequential; ColPali later only |
| ColPali deferred | Does not block current ingest |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Stage2 Markdown in final txt (limit-1) | 1 | Always per-page polish; segmenter chrome strip |
| `polish parse partial` | 1 | Accept complete `\documentclass` body without markers |
| CUDA assert in `_sample` / multinomial | 1 | Force `do_sample=False`; default temperature 0 |
| Stage3 OOM after Surya v2 success | 1 | Call manager.stop (insufficient alone) |
| Stage3 OOM (same) | 2 | `docker stop surya-vllm-*` + GPU headroom wait in `release()` |
| Dual `run_ocr_pipeline` PIDs during monitor | note | Avoid concurrent runs on 12GB |
| B `/usr/local` Ollama missing `llama-server` (hung curl install) | 1 | Userspace install `~/opt/ollama` via `wave2-ollama-userspace.sh` |
| B `python3 -m venv` fails (no ensurepip / python3-venv) | 1 | Install `uv` in keith home; `uv venv` for agent |
| `qdrant-client` 1.18: no `.search()` | 1 | Use `query_points` in `query_agent.py` |

## Next Action (OCR / TeX lane only)
1. Optional: GPU smoke — one doc with FIGURE → pageir figure + publish+ingest (`--reindex`); VRAM gate first
2. Do **not** start ColPali
3. Optional later: commit remaining unrelated OCR/question_paper/scorecard work when asked
4. Homelab Wave 2 — **out of lane** (already green)

## Next Action (Homelab / Linux lane only)
1. Wave 2 **complete** — idle unless ops asked
2. Keep Z: / keys / backups healthy; OCR lane may publish/ingest via CLI
3. Do not edit OCR engines / TeX quality work
4. Do not start SearXNG / Grafana / teacher Chat on B
5. After reboot B: `ollama serve` is session-only (not auto); re-start if agent needed
