# Token-Efficient Double Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Sol-High the reasoning owner and restrict Luna-Max to token-heavy, low-reasoning, mechanically verifiable work while limiting agent-triggered auto-review.

**Architecture:** Keep generic delegation and review rules in the global `double-agents` skill. Keep only OCR-specific restrictions in repository `AGENTS.md`. Use compact Luna handoffs and risk-triggered Sol review so saved context is not reread by default.

**Tech Stack:** Markdown skill instructions, YAML skill metadata, repository `AGENTS.md`.

---

### Task 1: Replace the global Double Agents policy

**Files:**
- Modify: `C:/Users/a1217/.codex/skills/double-agents/SKILL.md`

- [ ] **Step 1: Replace the current policy with concise role and gate rules**

The completed file must contain these sections and rules:

```markdown
## Goal
Reduce token use while keeping final quality equal or only slightly lower.

## Roles
`sol-high` owns requirements, reasoning, architecture, decomposition, risk,
integration, acceptance, and the final response.

`luna_max` handles only bounded, token-heavy, low-reasoning work: large
searches, structured summaries, exact repetitive edits, patterned tests,
validation commands, and log condensation.

## Delegation gate
Delegate only when all conditions are true: one objective; exact files and
method; deterministic acceptance and validation; substantial expected token
cost; no ambiguity, security, public API, schema, destructive, architecture,
or algorithm decision.

## Review and auto-review
Use Level 0 for read/search/test results, Level 1 for focused mechanical diffs,
and Level 2 only for failure, scope drift, or risk. Use zero auto-reviews for
read-only or low-risk mechanical work, at most one per implementation batch,
and a second only for explicit high-risk triggers. Never exceed two per user
request or create recursive review loops.
```

Also include one-retry escalation, a concrete delegation template, and a
compact Luna report format. Remove permission for Luna to select bug-fix or
implementation strategies.

- [ ] **Step 2: Verify the global skill contract**

Run:

```powershell
rg -n "sol-high|luna_max|all conditions|one retry|Level 0|at most one|Never exceed two|recursive review" C:\Users\a1217\.codex\skills\double-agents\SKILL.md
```

Expected: every required policy is present; no long raw-log or full-file report
requirement exists.

### Task 2: Update skill interface metadata

**Files:**
- Modify: `C:/Users/a1217/.codex/skills/double-agents/agents/openai.yaml`

- [ ] **Step 1: Replace interface copy with the new compact contract**

Use this exact YAML:

```yaml
interface:
  display_name: "Double Agents"
  short_description: "Sol directs; Luna executes low-reasoning token-heavy work"
  default_prompt: "Use $double-agents: keep reasoning and integration with sol-high; delegate only bounded, mechanical, verifiable, token-heavy work to luna_max; use compact reports and limited auto-review."
```

- [ ] **Step 2: Verify model names and interface fields**

Run:

```powershell
rg -n "display_name|short_description|default_prompt|sol-high|luna_max|limited auto-review" C:\Users\a1217\.codex\skills\double-agents\agents\openai.yaml
```

Expected: one interface block with all three fields and both model names.

### Task 3: Add the OCR repository addendum

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Append one concise Double-agent policy section**

Append rules that:

```markdown
## Double-agent policy

- `sol-high` owns reasoning, architecture, integration, acceptance, and final output.
- Delegate to `luna_max` only when every global `$double-agents` gate passes.
- Luna may search, summarize, make exact repetitive edits, add patterned tests,
  run validation, and condense logs.
- Luna must not choose the locked MCQ architecture, model selection, quality
  gate, ingest policy, Q1--Q45 coverage behavior, or run concurrent GPU OCR.
- Sol reviews read-only work from compact evidence, mechanical edits with a
  focused diff and tests, and takes full control only on failure, drift, or risk.
- Batch related work. Default to zero auto-reviews; use at most one per
  implementation batch and two only for explicit high-risk triggers.
```

Do not change any existing OCR rule.

- [ ] **Step 2: Inspect the focused repository diff**

Run:

```powershell
git diff -- AGENTS.md
```

Expected: the new section is appended; pre-existing user changes remain intact.

### Task 4: Cross-file validation

**Files:**
- Verify: `C:/Users/a1217/.codex/skills/double-agents/SKILL.md`
- Verify: `C:/Users/a1217/.codex/skills/double-agents/agents/openai.yaml`
- Verify: `AGENTS.md`

- [ ] **Step 1: Check required policy terms across all files**

Run:

```powershell
rg -n "sol-high|luna_max|auto-review|focused diff|concurrent GPU OCR|Q1--Q45" C:\Users\a1217\.codex\skills\double-agents\SKILL.md C:\Users\a1217\.codex\skills\double-agents\agents\openai.yaml AGENTS.md
```

Expected: generic rules appear in the global skill; OCR-only restrictions appear
in `AGENTS.md`.

- [ ] **Step 2: Confirm no OCR implementation file was modified by this task**

Run:

```powershell
git status --short -- AGENTS.md 2_生產線/2026-08-03-double-agents-token-efficient-routing-design.md 2_生產線/2026-08-03-double-agents-token-efficient-routing-plan.md
```

Expected: only `AGENTS.md` and the two new policy documents are reported for
repository-scoped work. Do not commit; repository rules require explicit user
authorization.
