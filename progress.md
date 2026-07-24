# Progress Log

## 2026-07-24 — Ingest contract implemented (figure + batch)
- Slice A: `crop_relpath` in pageir; stage/publish `figures/`; ingest `pageir_v2` + payload `crop_path`.
- Slice B: `figure_caption.py`; DynamicRouter FIGURE path; finalize merge; trunk `skip_figures: false`.
- Slice C: `python -m ocr_pipeline.batch_export --docs … --publish --ingest`.
- Tests: **32 passed** (content_first / job_export / done / ingest_segments / publish_figures / figure_caption / batch_export).
- Lazy `ocr_pipeline.__init__` + deferred factory import in `run_ocr_pipeline` so light tests need no torch.

## 2026-07-24 — Explored publish/ingest/pageir/figure surfaces
- Mapped `homelab/ingest/{done,publish,ingest}.py`, `job_export.py`, pageir writers, content_crop vs block crops, Qdrant upsert fields.
- Confirmed design gaps vs `2026-07-24-trunk-qwen-ingest-contract-design.md`: no figure segments, no `pageir_v2`, no batch CLI, stage/publish ignore `figures/`.
- Logged details in `findings.md`.

## 2026-07-24 ~06:44 — Homelab Wave 2 complete (user asleep; SSH hung)
- Fixed broken system Ollama (missing `llama-server`) via userspace `~/opt/ollama` (0.32.3).
- Models: `llama3.2:1b` + `nomic-embed-text`; CUDA on GTX 1660 SUPER; **not** on boot.
- Agent smoke PASS: reader upsert 403; hits `wave1demo`; answer returned.
- Flag: `/data/pdf-scaner/backups/wave1-scripts/WAVE2_B_DONE` = `2026-07-23T22:44:15Z`.
- Docs: `DATA_PLANE.md` Wave 2 green; compose stays Qdrant-only; Phase H2 complete.

## 2026-07-24 00:55 — Stop for the day (brainstorm locked)
- Spec approved + committed: `docs/superpowers/specs/2026-07-24-trunk-qwen-ingest-contract-design.md` (`89d8c37`).
- Locks: trunk **Qwen2.5-VL**; ingest = text + figure crop+caption (DONE v1, `pageir_v2`); batch publish from `output/`; formula knives only; **ColPali deferred**.
- **Next session:** writing-plans → implement figure path + batch CLI (do not start ColPali).
- Earlier today: question_paper mode, 789×3 scorecard, layout bakeoff (MinerU≈DocLayout ~5s; MinerU best formula typing; Surya cold ~221s).

## 2026-07-24 00:42 — Layout Stage1 bakeoff (789 content PNG)
- DocLayout 5.126s / 6 blocks (formula→other); MinerU 5.059s / 4 blocks (**equation**); Surya v2 220.9s cold Docker / 5 blocks (no equation).
- Verdict: **fastest ≈ MinerU & DocLayout**; **most precise for formula routing = MinerU**; Surya cold-start not comparable for speed.

## 2026-07-24 00:27 — 789.pdf full (1p) × 3 branches + scorecard
- Clarified: earlier only Qwen had `question_paper`; now **all three** use content crop via `config/branches/*.yaml`.
- Copied `data/sources/789.pdf` (1 page = full doc).
- Runs (VRAM clear ~1.3 GiB used before each):
  - qwen-vl question_paper: total **23.460s** → near-golden stems, compile pass
  - got-ppocr crop+engines: total **25.365s** → broken formulas, compile pass
  - mineru-ppocr crop+engines: total **25.555s** → one good frac, prose messy, compile pass
- Scorecard section A updated in `docs/superpowers/evals/p-ocr-branch-scorecard.md`. Rank: qwen ≫ mineru > got.

## 2026-07-24 00:19 — question_paper mode (789.pdf smoke)
- Added `content_crop.py`, `question_paper.py`, `QUESTION_PAPER_PROMPT`, `--doc-type question_paper`.
- Unit tests: `tests/test_question_paper.py` **7 passed**.
- Smoke: VRAM pre-check ~2.0/12.3 GiB used (OK) → `789.pdf` limit-1 → `output/789.qp.txt`:
  - 甲部(1)(35分) + Q1 frac + Q2 Ax=(4x+B)C; no margin warning. total≈58.4s.
- Default `doc_type` remains `marking_scheme`.

## 2026-07-23 23:58 — Human scorecard filled (qwen / got / mineru)
- Filled `docs/superpowers/evals/p-ocr-branch-scorecard.md`.
- Rank: **qwen-vl** (12 formula / 7 min prose / compile pass) ≫ mineru-ppocr (14 / 10 / fail, limit-1) > got-ppocr (22 / 12 / fail, limit-1).
- Caveat: got/mineru are limit-1 + skip_polish; not full-doc vs qwen.
- VRAM pre-check: 1757/12282 MiB free OK (no re-OCR this step).

## 2026-07-23 23:56 — OCR must use GPU MCP before runs
- Locked Habit 7 in `.cursor/rules/tool-routing.mdc`: pre/mid/post OCR VRAM checks + free-MiB adjust table.
- Live check: RTX 4070 SUPER used 1678/12282 MiB — headroom OK.

## 2026-07-23 23:55 — Hand-smoke publish→ingest (no OCR re-run)
- Loaded `%USERPROFILE%\.homelab\qdrant.a.env`; staged existing `output/123.*`
- `PUBLISHED Z:\jobs\20260723-155417-123` → `UPSERTED 801/801` into `exam_segments_v1` (exit 0)
- Bridge verified live; next: human scorecard or commit e2e when asked

## 2026-07-23 23:47 — OCR → publish → ingest e2e
- Added `src/ocr_pipeline/job_export.py` (stage tagged artifacts → `{doc_id}.*`, call publish/ingest).
- `run_ocr_pipeline.py`: `--doc-id`, `--publish`, `--ingest`, `--share-root`, `--job-dir`, `--reindex`.
- `homelab.ingest` importable; `uv` group `ingest` (qdrant-client, fastembed); qdrant import lazy.
- Tests: `test_job_export.py` + updated `test_done_schema.py` → **10 passed**. No live Z:/Qdrant in CI.

## 2026-07-23 23:41 — Agent lane split
- User locked ownership: **OCR agent = OCR + TeX output only**; **Homelab agent = Linux / data plane**.
- Recorded in `task_plan.md` (both Next Action sections) and `handoff.md` (Agent lanes + Wave 1 green 835).
- Homelab agent: idle on Wave 1; Wave 2 closed; will not touch engines/TeX.

## 2026-07-23 — Repo cleanup (A+B delete, D integrate)
- Deleted: pytest/golden logs, `golden_run_cf_report.txt`, `2015ans.pdf`, `.superpowers/`, output install/sync logs; cleared OneDrive phantom M files.
- Integrated: `TODOS.md` → `task_plan.md` backlog; `UPGRADE_NOTES.md` → `findings.md`; README → uv.
- Deferred: root CLI → `python -m ocr_pipeline`. `.gitignore` adds `pytest_*.txt`, `.superpowers/`.

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

## 2026-07-22 21:07 — dual-PC design review iteration 2
- Reviewed the updated design at `~/.gstack/projects/pdf-scaner/a1217-main-design-20260722-210437.md`.
- Iteration-1 changes are present: Tailnet/API-key posture, DONE contract, Samba-only, A-side embedding, Snapshot API, MCP read-only guidance, Wave-2 gates, and B resource budget.
- Remaining blockers are documented in `findings.md`: atomic sync/publication, precise manifest/key/backup/network implementation contracts, Qdrant Point-ID validity, and A-side resource controls.
