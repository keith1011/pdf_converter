# Figure-line agent guidance

This repository is the Figure line. Keep the three-stage layout stable:

- `1_收集資料/` is collection data and collection-only helpers.
- `2_生產線/` is production source, configuration, tests, and operational scripts.
- `3.分析結果/` is generated output, documentation, evaluation, reports, and local storage.

Run commands from the repository root. Project metadata remains at the root;
do not move `.git`, virtual environments, caches, or the historical
`3.分析結果/_opencode_export/` snapshot.

Before changing runtime behavior, read the current handoff under
`3.分析結果/docs/FIGURE_PIPELINE_HANDOFF.md` and inspect the relevant tests under
`2_生產線/tests/`. Keep path references aligned with the three-stage layout.

Existing project TODO: audit the test harness
(`test/tests/__mkdir_tmp__-test).ts`) before merging it into the permanent suite.

Plan and refine with the planning skill before each work phase; start each new
phase fresh after approval and do not overlap unrelated hotfixes.
