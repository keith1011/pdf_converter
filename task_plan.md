# Task Plan: PDF Scaner — content-first OCR → 可編輯 TeX → 可選編譯

## Goal
PDF → content-first 草稿（`.tex` + `.txt` + `.pageir.json`）→ 可選 `--check-compile` PDF；教師 ≤10 分鐘手改後可 reuse。

## Current Phase
**Task 4: wire engine factory/router/pipeline** — complete and verified; preserve existing combined-layout call sites while adding split engine wiring

## Hardware / model

| Item | Decision |
|------|----------|
| GPU | RTX 4070 Super **12GB** |
| Default VLM | **Qwen2.5-VL-7B-Instruct 4bit** |
| Decode | **greedy only** (`do_sample=False`) — sampling → CUDA multinomial assert |
| Token budgets | Stage3 polish **2048**; Stage2 route **1024** (`max_new_tokens_route`) |
| Surya v2 | Docker/vLLM OK for layout；**`release()` must `docker stop surya-vllm-*`** before VLM |
| Order | Layout → **stop vLLM** → Stage2/3 Qwen → content-first finalize → optional compile |

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

### Task 8: MinerU + UniMERNet experiment — in progress
- [x] Add lazy, fail-loud MinerU `LayoutEngine` and UniMERNet `FormulaEngine`
- [x] Wire `mineru` / `unimernet` factory selections; retain Surya/VLM defaults
- [x] Add CPU-only mocked adapter and factory tests
- [ ] Run focused CPU tests and commit source package on `main`
- [ ] Create `mineru-ppocr` config branch, commit it, then return to `main`

| Error | Resolution |
|-------|------------|
| Initial focused pytest invocation returned no terminal exit status. | Re-run after implementation and record the explicit result. |
| Task 6 focused pytest invocation returned no terminal exit status twice. | `cmd.exe` fallback also returned no status; report the terminal limitation and leave test/commit verification to the parent. |
| Task 7 requested pytest glob was not expanded by PowerShell/pytest. | Ran the four explicit matching test files; 7 passed. |
| Task 7 GPU smoke dependencies are absent (`doclayout_yolo=False`, `paddleocr=False`). | Skip model download/install to avoid multi-GB unbounded work; mark DONE_WITH_CONCERNS. |
| PowerShell rejected the Bash-style `&&` in a diff validation command. | Ran the validation command separately using PowerShell-compatible execution. |
| The Windows WSL `bash` shim has no `/bin/bash`, so the required Bash heredoc commit form cannot run. | Use PowerShell's native multiline string to pass the same one-line commit message. |
| Task 8 focused pytest invocation returned no shell exit status. | Record the terminal limitation; do not claim the CPU suite passed without an explicit result. |

### Phase 2.5b: LayoutArtifact resume — complete (via 2.8)
- [x] Persist LayoutBlock JSON; resume route/polish without re-Surya
- **Status:** complete (see Phase 2.8)

### Phase Ship 2: OCR overlay PDF — pending

### Phase H0: Homelab Wave 0 (PC-B data plane) — complete
- [x] Design APPROVED (`a1217-main-design-20260722-210437.md`)
- [x] OS: Ubuntu 24.04 on SATA (`homeserver` / `keith`); Windows kept on M.2
- [x] Repo scaffold: `homelab/`
- [x] Docker + Qdrant; from A: `curl http://192.168.1.107:6333/readyz`
- [x] Tailscale SSH: `keith@100.101.145.120`
- [x] Samba `\\192.168.1.107\pdf-scaner` mapped on A
- [x] Cursor MCP → B (`QDRANT_URL` + reader key + read-only); collections empty (fresh)
- **Status:** Wave 0 complete

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

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Stage2 Markdown in final txt (limit-1) | 1 | Always per-page polish; segmenter chrome strip |
| `polish parse partial` | 1 | Accept complete `\documentclass` body without markers |
| CUDA assert in `_sample` / multinomial | 1 | Force `do_sample=False`; default temperature 0 |
| Stage3 OOM after Surya v2 success | 1 | Call manager.stop (insufficient alone) |
| Stage3 OOM (same) | 2 | `docker stop surya-vllm-*` + GPU headroom wait in `release()` |
| Dual `run_ocr_pipeline` PIDs during monitor | note | Avoid concurrent runs on 12GB |

## Next Action
1. Commit Phase 2.8 when user asks (tokens + layout artifact + lock + tests)
2. Optional: full OCR re-run with `--reuse-layout` after one layout write / new TABLE_ROUTER
3. Homelab follow-ups still uncommitted under `homelab/`
4. Rotate Qdrant writer key when convenient
