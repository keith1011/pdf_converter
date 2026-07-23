# Progress Log

## 2026-07-23 — handoff.md 依 2026-07-23 北辰/Approach B 架構覆寫
- Goal/topology/data ownership/Homelab/Pitfalls 對齊 北辰（題庫→AI 老師 Chat；OCR 只是原料）
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
1. Optional: full 14-page OCR re-run with new TABLE_ROUTER + `--check-compile`
2. Phase 2.8 speed (tokens / LayoutArtifact resume)
3. Homelab follow-ups (still uncommitted under `homelab/`)

## 2026-07-23 — Commit greedy / VRAM / TABLE_ROUTER package
- Scoped commit: greedy decode, `layout.release` docker stop, TABLE_ROUTER linear + segmenter/integrity/content-first defenses, `temperature: 0.0`, related tests, planning docs + `handoff.md`
- Excluded: OneDrive phantom M files (empty numstat), `homelab/`, pytest/golden report artifacts, `.cursor/`
- User chose priority 1 from handoff next-actions

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

## 2026-07-22 21:07 — dual-PC design review iteration 2
- Reviewed the updated design at `~/.gstack/projects/pdf-scaner/a1217-main-design-20260722-210437.md`.
- Iteration-1 changes are present: Tailnet/API-key posture, DONE contract, Samba-only, A-side embedding, Snapshot API, MCP read-only guidance, Wave-2 gates, and B resource budget.
- Remaining blockers are documented in `findings.md`: atomic sync/publication, precise manifest/key/backup/network implementation contracts, Qdrant Point-ID validity, and A-side resource controls.
