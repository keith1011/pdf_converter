# Token-Efficient Double Agents Design

## Goal

Reduce token use while keeping final quality equal or only slightly lower.
Sol-High remains the sole reasoning and integration owner. Luna-Max handles
high-token, low-reasoning work with deterministic validation.

## Scope

Update three files:

- global `double-agents/SKILL.md`;
- global `double-agents/agents/openai.yaml`;
- repository `AGENTS.md`.

Do not change OCR code, pipeline configuration, CCR, or model endpoints.

## Roles

Sol-High owns requirements, architecture, decomposition, risk decisions,
integration, acceptance, and the final response.

Luna-Max may perform only bounded mechanical work: large searches, structured
summaries, explicitly specified repetitive edits, patterned tests, validation
commands, and log/result condensation. It must not choose architecture,
algorithms, API or schema behavior, security policy, destructive actions, or
fix strategies for ambiguous failures.

## Delegation Gate

Delegate only when every condition is true:

- objective and files are explicit;
- method is specified and needs little judgment;
- acceptance criteria and validation are deterministic;
- task is expected to consume substantial context or tokens;
- no security, public API, schema, destructive, or ambiguous decision exists.

Luna receives one objective, exact scope, forbidden changes, acceptance
criteria, and validation commands. It may retry once only when the failure and
correction are mechanical; otherwise it returns control to Sol.

## Compact Handoff

Luna returns only changed files, a 3--8 point diff summary, validation results,
and blockers. Avoid full-file dumps, long logs, and raw search output.

## Review Policy

Use graded review:

- Level 0: read/search/test tasks; Sol reads the compact result only.
- Level 1: mechanical edits; Sol checks a focused diff and validation.
- Level 2: failed validation, scope drift, or risk; Sol takes full control.

Agent-triggered auto-review is limited as follows:

- planning, read-only, documentation, and test-only work: zero;
- low-risk mechanical edits: focused diff and tests, normally zero;
- implementation batches: at most one;
- a second review is allowed only for P0/P1 findings, persistent validation
  failure, security/API/schema/data-migration/concurrency risk, or substantial
  rewrite;
- never review every subtask separately or create recursive review loops;
- maximum two auto-reviews per user request or implementation cycle.

## Repository Rules

The repository addendum allows Luna to search, apply exact repetitive edits,
run focused tests, and summarize logs. Luna must not change the locked MCQ
architecture, model selection, quality gate, ingest decisions, or Q1--Q45
coverage policy. GPU OCR remains visible and sequential; two pipelines must
never run together. Sol verifies the focused diff and required coverage.

## Acceptance

- Global skill language is concise and names `sol-high` and `luna_max`.
- Delegation requires all gate conditions.
- Luna cannot make reasoning-heavy or scope-expanding decisions.
- Compact handoff, graded review, retry limit, and auto-review caps are explicit.
- Repository rules preserve the locked OCR contract.
- No OCR implementation or configuration file changes.
