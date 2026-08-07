# Run production

Use this guide for Figure/OCR architecture, implementation, configuration,
tests, debugging, and pipeline execution.

## Skill routing

Use only what the task needs:

- `superpowers:brainstorming`: clarify ambiguous behavior or architecture.
- `double-agents`: scoped implementation with primary-agent review.
- `context7-mcp`: current dependency, SDK, API, or CLI documentation.
- `superpowers:test-driven-development`: behavior changes and bug fixes.
- `systematic-debugging`: failures with an unknown root cause.
- `superpowers:verification-before-completion`: final validation.

Read the selected skill before acting.

## Workflow

1. For runtime changes, read
   `3.分析結果/docs/FIGURE_PIPELINE_HANDOFF.md` and the relevant tests.
2. Plan the phase and obtain any required approval before implementation; do not
   mix unrelated hotfixes.
3. Change code under `src/`, configuration under `config/`, operational helpers
   under `_script/`, and tests under `tests/`.
4. Run commands from the repository root and verify the smallest relevant suite,
   then broader regression tests when risk warrants it.
5. Write generated artifacts to `3.分析結果/`, never into source directories.

Keep MinerU/Qwen/PaddleOCR paths aligned with the three-stage layout. Project
TODO: audit `test/tests/__mkdir_tmp__-test).ts` before permanent test-suite use.
