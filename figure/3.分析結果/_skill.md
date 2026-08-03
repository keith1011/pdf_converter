# Analysis and results stage

Purpose: store and review outputs produced by collection and production.

Contents:

- `3.分析結果/output/`: OCR, PageIR, Figure B1/B2 bundles, overlays, and logs.
- `3.分析結果/evals/`: evaluation and scorecard material.
- `3.分析結果/docs/`: handoffs, progress, specifications, and test-harness audits.
- `3.分析結果/reports/`: root-level findings, progress, handoff, debug, and TODO reports.
- `3.分析結果/qdrant_storage/`: local Qdrant runtime storage.
- `3.分析結果/_opencode_export/`: immutable historical export snapshot.
- `3.分析結果/_scripts/`: report validation/revision placeholders.

Rules:

1. Treat artifacts as reviewable results; do not edit source PDFs here.
2. Use `____validate_report.js` and `____revise_report.js` as report-stage hooks.
3. Figure B2 review status belongs in the generated bundle under `output/` and
   must not be silently changed in prose-only reports.
