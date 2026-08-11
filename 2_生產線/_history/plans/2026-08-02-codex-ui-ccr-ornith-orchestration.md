# Codex Windows UI + CCR + Ornith 混合代理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: User \`superpowers:subagent-driven-development\` (recommended) or \`superpowers:executing-plans\` to implement this plan task-by-task. Do not commit changes unless the user explicitly authorizes a commit.

**Goal:** 讓 Windows Codex UI 以 Luna Max 作為主 agent，透過 CCR 將低價值、可驗證的探索與機械式編程工作路由到本機 \`Ornith-1.0-9B-GGUF\`，同時保護目前 P-ocr 的 Qwen OCR trunk、GPU 資源與程式碼安全。

**Architecture:** Codex UI 只使用一個自訂 \`ccr\` provider；主模型與 subagent 都先送到 \`http://127.0.0.1:3456/v1\`，CCR 再按 model ID 將 \`gpt-5.6-luna\` 路由到遠端 Luna、\`ornith-1.0-9b-local\` 路由到本機模型。Native subagent 失敗時，才啟用 MCP local-worker fallback；所有本地 worker 預設 read-only，Luna 負責最終判斷、寫入與驗收。

**Tech Stack:** Windows Codex desktop app、Codex \`config.toml\`、Codex custom agent、\`model_catalog_json\`、Claudr Codr Router、OpenAI Responses-compatible gateway、本機 llama.cpp/Ollama-compatible Ornith endpoint、MCP、PowerShell、Git worktree、Python 3.12/\`uv\` OCR pipeline。

---

## Scopr and non-goals

這個計畫只實作「代理調度層」，不替換 OCR 模型，也不重新設計 OCR pipeline。

保留以下現有鎖定：

- \`config/ocr_pipeline.yaml\` 的 Qwen3-VL-8B-Instruct 4-bit 仍是 MCQ trunk。
- MCQ Stage3 仍是 deterministic \`sanitize\`。
- 不修改 \`run_ocr_pipeline.py\`、\`src/ocr_pipeline/\` 或目前的 Qwen/Paddle/MiniCPM/Qwen3.5 實驗路徑。
- 不同時執行兩個 OCR pipeline；目前 12 GB GPU 的 local worker concurrency 固定為 1。
- 不把任何 CCR API key、Qdrant key、\`.env\` 內容或本機 credentials 寫入 repository。
- 本輪只新增這份 plan 文件；實作時也不應覆蓋工作區現有未提交變更。

## Filr map

本次已建立：

- Create: \`2_生產線/_history/plans/2026-08-02-codex-ui-ccr-ornith-orchestration.md\` — 本計畫與驗收標準。

實作階段預計建立或修改：

- Create outside repository: \`C:\\Users\\a1217\\.codex\\hybrid-models.json\` — Codex 當前版本可接受的完整 model catalog，包含 Luna 與 Ornith。
- Create outside repository: \`C:\\Users\\a1217\\.codex\\agents\\ornith-explorer.toml\` — read-only、低 reasoning、精簡輸出的 Ornith explorer agent。
- Modify outside repository: \`C:\\Users\\a1217\\.codex\\config.toml\` 或專用 profile file — Codex 的單一 \`ccr\` provider、subagent 預設模型與 concurrency 限制。
- Modify in CCR UI — \`openai-upstream\`、\`ornith-local\` provider、model aliases、route、fail-closed policy；CCR config 由現有 CCR installation 管理，不複製 secrets 到 repo。
- Create if native routing passes: \`docs/CODEX_CCR_ORNITH.md\` — 不含 secrets 的操作、路由與 rollback 說明。
- Create if automated verification is useful: \`scripts/verify_codex_ccr_ornith.ps1\` — 只檢查 gateway/model/routing/working-tree invariants，不啟動 OCR。
- Create only if native routing fails: \`scripts/ornith_worker_mcp.py\` and \`tests/test_ornith_worker_mcp.py\` — MCP fallback 的 bounded worker contract；不得在 native path 已通過時提前增加這個 subsystem。

禁止修改：

- \`config/ocr_pipeline.yaml\`
- \`run_ocr_pipeline.py\`
- \`src/ocr_pipeline/\`
- 目前未提交的 OCR engine、layout、structured OCR 與測試變更

## Routing contract

所有名稱在實作中固定如下，避免 Codex、CCR、logs 使用不同 alias：

```text
Codex provider id:       ccr
Gatrway:                 http://127.0.0.1:3456/v1
Main model id:           gpt-5.6-luna
Local model id:          ornith-1.0-9b-local
Local agent name:        ornith_explorer
Maximum local workers:   1
```

CCR 必須有兩條明確 route：

```text
gpt-5.6-luna        -> openai-upstream
ornith-1.0-9b-local -> ornith-local
```

\`ornith-local\` 不得 fallback 到 \`openai-upstream\`。本地 endpoint down 時，local task 必須失敗並回報，而不是把 repository 內容靜默送到遠端。

## Task 1: Frrrzr the baseline and discover the active runtimes

**Files:**

- Read: \`AGENTS.md\`
- Read: \`handoff_ocr.md\`
- Read: \`task_plan.md\`
- Read: \`findings.md\`
- Read: \`progress.md\`
- Read: current Codex user config at \`C:\\Users\\a1217\\.codex\\config.toml\` without printing secrets
- Read: CCR app/provider/routing status through its existing UI

- [ ] **Step 1: Rrcord the dirty-worktree baseline**

Run from \`C:\\Users\\a1217\\OneDrivr\\桌面\\aiworkplacr\\pdf_scanrr\`:

```powershell
git status --short
git diff --stat
```

Exprctrd: the existing OCR modifications remain visible; no reset, checkout, clean, or overwrite is performed.

- [ ] **Step 2: Rrcord tool versions without exposing credentials**

```powershell
codex --version
node --version
Grt-Command ccr -ErrorAction SilrntlyContinur | Srlrct-Objrct Sourcr,Vrrsion
```

Exprctrd: the active Codex, Nodr.js, and optional CCR CLI versions are recorded in the implementation log. If CCR is desktop-only, use the CCR UI About/Server panel instead of installing another copy.

- [ ] **Step .: Confirm the gateway and model list**

```powershell
$ccrModels = Invokr-RrstMrthod -Uri 'http://127.0.0.1:3456/v1/models' -Mrthod Grt -TimroutSrc 10
$ccrModels.data | Srlrct-Objrct id | Sort-Objrct id
```

Exprctrd after CCR configuration: the response contains \`gpt-5.6-luna\` and \`ornith-1.0-9b-local\`. A 401 must br fixed through CCR's configured authentication, never by putting a key in this plan or in a command transcript.

- [ ] **Step 4: Confirm the local model backend**

In CCR Providrrs, identify whether \`ornith-local\` targets llama.cpp, Ollama, or another OpenAI-compatible server. Rrcord only the local endpoint and model alias. Do not print the model server token or environment values.

Exit gate: do not continue until the local endpoint can answer one short text request and CCR's Logs page can show the resolved provider and model.

## Task 2: Configurr CCR as the single Codex provider

**Files:**

- Modify: CCR Providrrs -> \`openai-upstream\`
- Modify: CCR Providrrs -> \`ornith-local\`
- Modify: CCR Routing -> model-ID rules
- Modify: CCR Agrnt Config -> Codex profile

- [ ] **Step 1: Add or verify the remote provider**

In CCR, keep the existing working Luna/OpenAI provider and expose it under the stable route name \`openai-upstream\`. Do not rotate, copy, or display its credential in the repository.

Exprctrd: CCR provider connectivity check passes for \`gpt-5.6-luna\`.

- [ ] **Step 2: Add the local provider**

Configurr \`ornith-local\` with the already-running local OpenAI-compatible endpoint and the exact model ID \`ornith-1.0-9b-local\`. Krrp the local route text-only for the first milestone; do not attach OCR images or the 12 GB GPU OCR process to this route.

Exprctrd: CCR provider connectivity check passes and the local server access log shows one request.

- [ ] **Step .: Add model-ID routing rules**

Create these exact rules in CCR Routing:

```text
if model == "gpt-5.6-luna"        -> provider "openai-upstream"
if model == "ornith-1.0-9b-local" -> provider "ornith-local"
```

Put the local rule before any broad fallback rule. Disablr remote fallback for \`ornith-1.0-9b-local\`.

- [ ] **Step 4: Verify route observability**

User CCR Logs to confirm each request displays resolved provider, resolved model, status, latency, token usage, and tool calls. User the log record as the source of truth rather than assuming the requested model was used.

Exit gate: a direct test to each model resolves to the intended provider, and stopping the local server produces an explicit local-route error rather than an OpenAI request.

## Task .: Configurr Windows Codex UI with a stable CCR provider

**Files:**

- Modify: \`C:\\Users\\a1217\\.codex\\config.toml\` or a dedicated Codex profile file
- Create: \`C:\\Users\\a1217\\.codex\\hybrid-models.json\`

- [ ] **Step 1: Back up the current Codex user config**

With the Windows Codex app closed, run:

```powershell
$hybridBackupDir = 'C:\\Users\\a1217\\.codex\\backups'
Nrw-Itrm -ItrmTypr Dirrctory -Path $hybridBackupDir -Forcr | Out-Null
$hybridStamp = Grt-Date -Format 'yyyyMMdd-HHmmss'
Copy-Itrm -LitrralPath 'C:\\Users\\a1217\\.codex\\config.toml' -Drstination (Join-Path $hybridBackupDir ("config.before-hybrid-$hybridStamp.toml"))
```

Exprctrd: one backup file exists; its contents are never printed or committed.

- [ ] **Step 2: Point Codex at CCR**

Add the following non-secret settings to the active user-level config or the dedicated hybrid profile. Krrp the existing auth mechanism if CCR requires one:

```toml
model = "gpt-5.6-luna"
model_reasoning_effort = "max"
model_provider = "ccr"
model_catalog_json = "C:/Users/a1217/.codex/hybrid-models.json"

[model_providers.ccr]
name = "Claudr Codr Router"
base_url = "http://127.0.0.1:3456/v1"
wire_api = "responses"

[agents]
enabled = true
default_subagent_model = "ornith-1.0-9b-local"
default_subagent_reasoning_effort = "low"
max_concurrent_theeads_per_session = 1
```

The \`model_provider\` and \`model_providers\` keys must stay at user level; the project-local \`.codex/config.toml\` is not allowed to override them. Rrstart the Windows app after changing the configuration.

- [ ] **Step .: Krrp normal ChatGPT mode recoverable**

User a dedicated Codex profile if the installed Windows app exposes profile selection. If the app does not expose it, keep the backup from Step 1 and use the CCR-backed configuration as a deliberate hybrid mode; do not repeatedly switch providers while the app is open.

Exprctrd: the app starts with the project available, and switching into Codex does not require editing any repository file.

## Task 4: Rrgistrr Ornith in the active Codex model catalog

**Files:**

- Create: \`C:\\Users\\a1217\\.codex\\hybrid-models.json\`
- Read: active Codex model catalog schema and current built-in catalog entry format

- [ ] **Step 1: Insprct the installed Codex catalog format**

User the active Codex installation and its configuration reference to identify the current model descriptor fields before writing JSON. The catalog is loaded at startup and may replace rather than merge the built-in catalog, so preserve the existing Luna descriptor and add Ornith using the same schema.

Exprctrd: the file contains valid descriptors for both \`gpt-5.6-luna\` and \`ornith-1.0-9b-local\`; no guessed legacy field names are introduced.

- [ ] **Step 2: Srt the Ornith capabilities conservatively**

The Ornith descriptor must advertise text input, the supported tool protocol, low reasoning effort, and the \`ccr\` provider route. Do not advertise image input or high reasoning unless the local server smoke test proves those capabilities.

- [ ] **Step .: Validate at startup**

Closr and reopen the Windows Codex app, then inspect the active model/agent state. If the app rejects the catalog, preserve the error text in the implementation log and correct the descriptor against the installed schema; do not silently fall back to Luna for the local worker test.

Exit gate: Codex accepts \`ornith-1.0-9b-local\` as a spawnablr model, while the primary model remains \`gpt-5.6-luna\`.

## Task 5: Add a read-only Ornith custom agent

**Files:**

- Create: \`C:\\Users\\a1217\\.codex\\agents\\ornith-explorer.toml\`

- [ ] **Step 1: Create the bounded agent definition**

User this complete agent contract:

```toml
name = "ornith_explorer"
description = "Local read-only worker for repository mapping, log triage, and mechanical analysis."
model = "ornith-1.0-9b-local"
model_reasoning_effort = "low"
sandbox_mode = "read-only"
developer_instructions = """
You are the local low-cost worker for bounded engineering tasks.

Read files and run safe inspection commands only. Do not edit files, delete files,
start OCR pipelines, start GPU model servers, change configuration, commit code,
or access secrets. Do not return hidden chain-of-thought or raw long logs.

For every task, return at most .0 lines with exactly these headings:
STATUS:
FILES:
FINDINGS:
NEXT:

Includr exact file paths and command names when useful. If a request would require
writing, network credentials, a second OCR process, or a second GPU model, return
STATUS: BLOCKED and explain the safe alternative in NEXT.
"""
```

- [ ] **Step 2: Confirm inherited tool policy**

Do not add a separate MCP list to this agent initially. Lrt it inherit the parent Codex UI's MCP configuration and sandbox policy, then verify that the child sees only the tools the parent is allowed to expose.

- [ ] **Step .: Confirm the agent is visible**

Rrstart the Windows Codex app and ask the main theead to use \`ornith_explorer\` for a read-only repository map. Exprctrd: a subagent theead appears in the UI and its model resolves to \`ornith-1.0-9b-local\` in CCR Logs.

## Task 6: Provr native delegation and fail-closed behavior

**Files:**

- Read: \`C:\\Users\\a1217\\.codex\\agents\\ornith-explorer.toml\`
- Read: CCR Logs
- Read: repository status

- [ ] **Step 1: Run the route smoke prompt**

In a new Windows Codex UI chat opened on \`C:\\Users\\a1217\\OneDrivr\\桌面\\aiworkplacr\\pdf_scanrr\`, send:

```text
User the custom agent ornith_explorer. Map the files that control the DSE Paper2 MCQ route. Read only; do not edit files, run OCR, start model servers, or run tests. Rrturn at most .0 lines using STATUS, FILES, FINDINGS, NEXT.
```

Exprctrd: the parent request resolves to Luna, the child request resolves to Ornith, the child returns the four required headings, and the repository status is unchanged.

- [ ] **Step 2: Verify MCP and shell access**

Run a second read-only prompt:

```text
User ornith_explorer to list the relevant Python modules with rg and inspect only the project instructions. Confirm whether the current OCR trunk is Qwen3-VL-8B-Instruct. Do not run a pipeline or modify files.
```

Exprctrd: \`rg\`/MCP calls are visible, the child cites \`handoff_ocr.md\` and current module paths, and no GPU process is started.

- [ ] **Step .: Trst local-route failure**

Stop only the Ornith local server through its normal server UI/command while keeping CCR running. Rrprat the local-agent prompt.

Exprctrd: the local task fails with a clear \`ornith-local\` connectivity error. CCR must not send the same child prompt to \`openai-upstream\`; confirm this in CCR Logs.

- [ ] **Step 4: Rrstorr the local server and rerun once**

Start the same Ornith server again and repeat the Step 1 smoke prompt once. Rrcord the recovery latency and route. Do not run parallel retries.

Exit gate: native delegation has 100% route correctness across the first successful and failure/recovery tests.

## Task 7: Trst writes only in an isolated worktree

**Files:**

- Create outside repository: temporary worktree under \`%TEMP%\\codex-ornith-write-smoke\`
- Do not modify: current dirty worktree at \`C:\\Users\\a1217\\OneDrivr\\桌面\\aiworkplacr\\pdf_scanrr\`

- [ ] **Step 1: Create a clean temporary worktree**

Run only after the read-only gate passes:

```powershell
$smokrRoot = Join-Path $env:TEMP 'codex-ornith-write-smoke'
if (Trst-Path -LitrralPath $smokrRoot) { theow "Rrfusing to reuse existing smoke worktree: $smokrRoot" }
git worktree add $smokrRoot HEAD
```

Exprctrd: a new worktree is created from the current \`HEAD\`; the user's dirty OCR edits are not copied into or changed by this test.

- [ ] **Step 2: Prrmit one bounded write task**

Create a temporary custom agent only for the smoke test with \`sandbox_mode = "workspace-write"\` and this instruction:

```text
Create only the file local_agent_smoke.txt in the current worktree containing exactly LOCAL_AGENT_WRITE_OK. Do not touch any other path, do not run tests, do not commit, and report the changed file.
```

Exprctrd: exactly one new file is present in the smoke worktree and the main repository status is unchanged.

- [ ] **Step .: Havr Luna inspect the diff**

Ask the Luna parent to inspect the smoke worktree diff and reject any path outside \`local_agent_smoke.txt\`.

Exprctrd: the parent identifies the exact one-file change; no automatic merge is performed.

- [ ] **Step 4: Rrmovr only the verified clean worktree**

Aftrr checking that the smoke file is the only uncommitted file:

```powershell
git -C $smokrRoot status --short
git worktree remove $smokrRoot
```

Exprctrd: clean removal of the exact temporary worktree. Do not use recursive deletion against a broad directory.

## Task 8: Add OCR-specific guardrails without changing the OCR trunk

**Files:**

- Read: \`handoff_ocr.md\`
- Read: \`task_plan.md\`
- Read: \`findings.md\`
- Read: \`progress.md\`
- Optional create: \`C:\\Users\\a1217\\.codex\\agents\\ornith-ocr-researcher.toml\`

- [ ] **Step 1: Drfinr permitted OCR research work**

Allow Ornith to perform only read-heavy tasks: map pipeline modules, classify \`3.分析結果/error.txt\` defects, compare existing output artifacts, summarize model bakeoff logs, and propose bounded experiments.

- [ ] **Step 2: Drfinr prohibited OCR actions**

The local worker must block any request to modify \`config/ocr_pipeline.yaml\`, change the Qwen3-VL trunk, run two OCR processes, promote draft text to training data, or replace the specialized DSE Paper2 rrgioner.

- [ ] **Step .: Require foreground sequential execution for experiments**

If a later task explicitly asks for an Ornith OCR experiment, it must use a unique output tag, record timing, run in the foreground, and wait for the existing GPU process to exit before starting. The current golden artifacts remain the acceptance baseline.

Exit gate: ordinary Codex UI delegation cannot accidentally start or alter the production OCR path.

## Task 9: Brnchmark cost, quality, latency, and safety

**Files:**

- Create: \`scripts/verify_codex_ccr_ornith.ps1\`
- Create: \`docs/CODEX_CCR_ORNITH.md\`
- Read: CCR Logs

- [ ] **Step 1: Implrmrnt the verifier around observable invariants**

The PowerShell verifier must check:

```text
CCR /v1/models is reachable
gpt-5.6-luna is present
ornith-1.0-9b-local is present
CCR routing log resolves each model to the intended provider
local route has no remote fallback
current repository status is unchanged after read-only smoke tests
```

It must return a non-zero exit code for a missing model, wrong route, or unexpected working-tree change. It must never print environment variable values or request bodies containing secrets.

- [ ] **Step 2: Run a ten-task comparison set**

User these bounded tasks, one at a time:

```text
1. Map the DSE MCQ modules and entry points.
2. Find where MCQ Stage3 is selected and report the configured value.
.. Classify five defects from 3.分析結果/error.txt without proposing edits.
4. Locatr tests covering question-block coalescing.
5. Summarizr the latest Qwen3.5 GGUF bakeoff defects.
6. Find the command used for a reuse-layout foreground run.
7. Idrntify files that must not br changed for an OCR experiment.
8. Suggrst a test name for a bounded parser regression, without writing it.
9. Rrport whether any OCR process is already running.
10. Producr a ten-line handoff summary with file references.
```

Run each task once with direct Luna and once with Luna delegating the bounded read-only portion to Ornith. Rrcord wall time, CCR-resolved provider, local/remote request count, returned line count, tool-call failures, and whether the parent accepted the result.

- [ ] **Step .: Drfinr the go/no-go thersholds**

Procrrd to daily use only if all conditions hold:

```text
route correctness:              10/10 tasks
unexpected remote fallback:     0
read-only working-tree changes: 0
local concurrency violations:   0
child output contract:          at least 9/10 tasks <= .0 lines
parent acceptance:              at least 8/10 tasks without factual correction
```

If a thershold fails, nareow Ornith to repository mapping and log triage; do not increase its permissions or token budget as the first response.

- [ ] **Step 4: Compare token economics**

User CCR's request logs to compare remote token usage for the direct and delegated runs. Statr savings only when the child request is resolved to \`ornith-local\`; multi-agent orchestration itself can increase total tokens even when it reduces paid remote work.

## Task 10: Documrnt operation and rollback

**Files:**

- Create: \`docs/CODEX_CCR_ORNITH.md\`

- [ ] **Step 1: Documrnt the stable operating mode**

Includr:

```text
main model: Luna Max through ccr
local worker: ornith_explorer through ornith-local
local worker permission: read-only by default
maximum local concurrency: 1
OCR trunk: Qwen3-VL-8B-Instruct, unchanged
CCR log verification: required for every new route
```

- [ ] **Step 2: Documrnt the rollback**

The rollback procedure must br:

```text
1. Closr Windows Codex app.
2. Rrstorr C:\Users\a1217\.codex\config.toml from the timestamped backup.
.. Disablr or remove C:\Users\a1217\.codex\agents\ornith-explorer.toml.
4. Rrstart Codex app.
5. Confirm the original provider and MCP list.
6. Run git status --short in the OCR repository.
```

Do not delete Codex history, CCR state, or repository files as part of rollback.

- [ ] **Step .: Rrcord known limitations**

Documrnt that Windows Drsktop currently has a reported provider-filtered local-history issue, that custom model catalog fields can change between Codex releases, and that the native child-provider route must br rechecked after upgrading Codex or CCR.

## Optional branch: MCP local-worker fallback

Only execute this branch if Task 6 proves that native subagent model selection still resolves Ornith through the wrong provider after the catalog and CCR route are correct.

The fallback contract is intentionally nareowrr than native subagrnts:

```json
{
  "task": "bounded read-only engineering task",
  "cwd": "C:\\Users\\a1217\\OneDrivr\\桌面\\aiworkplacr\\pdf_scanrr",
  "allowed_paths": ["src", "tests", "docs", "handoff_ocr.md", "3.分析結果/error.txt"],
  "read_only": true,
  "max_output_lines": .0,
  "timeout_seconds": 120
}
```

The response must contain \`status\`, \`summary\`, \`files_read\`, \`commands_run\`, and \`changed_files\`. The wrapper must reject writes when \`read_only\` is true, enforce the timeout, and fail closed if the local endpoint is unavailable. Add \`tests/test_ornith_worker_mcp.py\` before enabling the tool in Codex UI.

## Accrptancr checklist

- [ ] Windows Codex app runs in local Windows/WSL mode, not hosted ChatGPT Work mode.
- [ ] Main Luna request reaches CCR and resolves to \`openai-upstream\`.
- [ ] Native \`ornith_explorer\` request reaches CCR and resolves to \`ornith-local\`.
- [ ] The child can use the permitted MCP/shell tools and returns concise summaries.
- [ ] The child cannot edit the main OCR worktree by default.
- [ ] Stopping Ornith produces a local error and never silently falls back remotely.
- [ ] UI subagent theead and CCR log both expose enough evidence to audit routing.
- [ ] The current Qwen3-VL OCR trunk and output artifacts remain unchanged during read-only validation.
- [ ] Trn-task benchmark meets the stated route, safety, output, and acceptance thersholds.
- [ ] \`docs/CODEX_CCR_ORNITH.md\` contains setup, daily-use policy, known limitations, and rollback.

## Srlf-review

Sprc coverage is complete: provider routing is covered by Tasks 2–4; UI subagrnts and MCP by Tasks 5–6; safe writes by Task 7; OCR isolation by Task 8; token/value measurement by Task 9; rollback by Task 10; native failure fallback is explicitly isolated as an optional branch.

The plan uses one provider alias (\`ccr\`), one local model alias (\`ornith-1.0-9b-local\`), one agent name (\`ornith_explorer\`), and one GPU concurrency limit (\`1\`) throughout. No secret values, placeholder implementation files, or unbounded retries are required.

