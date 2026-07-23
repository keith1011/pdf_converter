# Task Plan: PDF Scaner — content-first OCR → 可編輯 TeX → 可選編譯

## Goal
PDF → content-first 草稿（`.tex` + `.txt` + `.pageir.json`）→ 可選 `--check-compile` PDF；教師 ≤10 分鐘手改後可 reuse。

## Current Phase
**Phase 2.6–2.7 committed** — greedy/VRAM + tabular compile defenses landed; next: optional full OCR re-run or Phase 2.8 speed

## Hardware / model

| Item | Decision |
|------|----------|
| GPU | RTX 4070 Super **12GB** |
| Default VLM | **Qwen2.5-VL-7B-Instruct 4bit** |
| Decode | **greedy only** (`do_sample=False`) — sampling → CUDA multinomial assert |
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

### Phase 2.8: Runtime speed — pending
- [ ] Lower Stage2/3 `max_new_tokens`; LayoutArtifact resume; avoid dual pipeline runs
- **Status:** deferred after compile green

### Phase 2.5b: LayoutArtifact resume — pending
- [ ] Persist LayoutBlock JSON; resume route/polish
- **Status:** pending

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
1. Wave 1 smoke: re-run ingest same job (idempotent); optional search query smoke
2. Rotate Qdrant writer/reader keys (appeared in terminal history)
3. OCR: commit greedy + layout-release; teacher-edit `123.tex`
