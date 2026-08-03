---
name: double-agents
description: Use during implementation to keep sol-high responsible for reasoning and integration while luna_max executes token-heavy, low-reasoning, mechanically verifiable work.
---

# Double Agents

## Goal

Reduce token use while keeping final quality equal or only slightly lower.

## Roles

### sol-high

Owns requirements, reasoning, architecture, decomposition, risk decisions,
integration, acceptance, and the final response.

### luna_max

Handles only bounded, token-heavy, low-reasoning work:

- large searches and structured summaries;
- exact repetitive edits;
- patterned tests;
- validation commands;
- log and result condensation.

Never delegate architecture, algorithms, ambiguous fixes, public API or schema
behavior, security, destructive operations, or scope decisions.

## Delegation gate

Delegate only when all conditions are true:

- one concrete objective;
- exact files, method, and allowed changes;
- deterministic acceptance criteria and validation;
- substantial expected context or token cost;
- no ambiguity or prohibited decision.

If any condition fails, sol-high keeps the task.

## Delegation brief

```text
Objective: <one bounded result>
Files: <exact paths>
Method: <mechanical steps>
Allowed changes: <exact boundary>
Do not change: <architecture, APIs, schemas, unrelated files, destructive state>
Acceptance: <observable result>
Validation: <exact commands and expected result>
Report: changed files, 3-8 diff points, validation result, blockers
```

Replace every placeholder before dispatch.

## Retry and escalation

Luna may retry once only when the failure and correction are mechanical and
inside the brief. On ambiguity, failed validation, scope drift, or a required
design choice, stop and return control to sol-high.

## Compact report

Return only:

- changed files;
- a 3-8 point diff summary;
- validation commands and outcomes;
- blockers or scope concerns.

Avoid full-file dumps, long logs, and raw search output.

## Review

- Level 0: read, search, or test work; inspect compact evidence only.
- Level 1: mechanical edits; inspect a focused diff and validation.
- Level 2: failure, drift, or risk; sol-high takes full control.

Sol-high accepts or rejects all delegated work.

## Auto-review budget

- Planning, read-only, documentation, and test-only work: zero.
- Low-risk mechanical edits: focused diff and tests; normally zero.
- An implementation batch: at most one auto-review.
- A second review requires a P0/P1 finding, persistent validation failure,
  security/API/schema/data-migration/concurrency risk, or substantial rewrite.
- Never exceed two auto-reviews per user request or implementation cycle.
- Batch related tasks; never review every subtask or create recursive loops.
- luna_max never triggers auto-review unless the brief explicitly requires it.
