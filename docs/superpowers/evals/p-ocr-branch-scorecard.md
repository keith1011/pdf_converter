# P-ocr OCR Branch Comparison Scorecard

Compare the same golden input and shared output contract (`.tex`, `.txt`, `.pageir.json`) across these branches:

| Branch | Formula edits (score) | Prose edit min (score) | Compile (score) | Notes | layout_s (log) | text_s (log) | formula_s (log) | total_s (log) |
|--------|----------------------|------------------------|-----------------|-------|----------------|--------------|-----------------|---------------|
| qwen-vl | | | | | | | | |
| got-ppocr | | | | | | | | |
| mineru-ppocr | | | | | | | | |

## Scoring rules

- **Formula edits:** count manual formula-body corrections needed for the golden draft.
- **Prose edit min:** record the teacher's manual editing time in minutes.
- **Compile:** record whether the draft passes `--check-compile` (`pass` / `fail`).
- **Timing columns:** capture wall-clock stage timings from the run log only. They are **not ranking weights**.

## After each golden run

1. Run the branch against the same source PDF and settings; save its output and stage-timing log.
2. Use the resulting draft to count formula edits, time prose editing, and record the compile result.
3. Enter all values in the branch row, adding concise causes or anomalies in **Notes**.
4. Rank only from the scored columns above; use timings as operational context, not quality weight.

## References

- Spec: `docs/superpowers/specs/2026-07-23-ocr-engine-adapters-design.md`
- Plan: `docs/superpowers/plans/2026-07-23-ocr-engine-adapters.md`
