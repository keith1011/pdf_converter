# Analyze results

Use this guide for output review, evaluation, benchmarks, reports, handoffs, and
documentation.

## Skill routing

Use only what the task needs:

- `qa-only`: read-only inspection and evidence-backed findings.
- `qa`: validation plus fixes when changes are authorized.
- `benchmark` or `benchmark-models`: performance or model comparison.
- `code-review-skill`: review production changes before acceptance.
- `document-generate`: create or update structured reports and handoffs.
- `pdf:pdf`: inspect PDF result artifacts.

Read the selected skill before acting.

## Workflow

1. Inspect evidence under `output/` and evaluation material under `evals/`.
2. Keep reproducible measurements, commands, and source artifact paths in the
   report.
3. Put reports and handoffs under `reports/` or `docs/`; use `_scripts/` for
   repeatable validation and revision.
4. Record Figure B2 review state in its generated bundle under `output/`, not
   only in prose.
5. Send required code/config changes back to `2_生產線/` and source-data issues
   back to `1_收集資料/`.

Do not edit source PDFs here. Treat `qdrant_storage/` as runtime state and
`_opencode_export/` as an immutable historical snapshot.
