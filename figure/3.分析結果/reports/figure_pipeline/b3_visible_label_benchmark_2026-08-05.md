# Phase B3 Visible-label OCR Benchmark — 2026-08-05

## Scope

This is a six-sample, multi-shape benchmark for the local
`Qwen/Qwen3-VL-8B-Instruct` 4-bit B3 label OCR path. The samples were selected
from the preserved DSE question crops and isolated with the B1 manual-bbox
fallback because the 2012–2022 layout manifests expose each question as a
`text` block rather than a figure block.

The benchmark does not modify source crops or the Q18 acceptance artifacts.
Each stage publishes a new sibling bundle. The original model proposal remains
inside the pending B3 bundle; only the human-reviewed sibling exposes
top-level `visible_labels`.

## Samples

| Sample | Shape focus | B1 source | B2 reviewed input |
|---|---|---|---|
| 2012p2-q016 | sector and annular arc | `output/figure_pipeline/benchmark/2012p2-q016-b1` | `.../2012p2-q016-b2-reviewed` |
| 2012p2-q020 | circle and cyclic quadrilateral | `.../2012p2-q020-b1` | `.../2012p2-q020-b2-reviewed` |
| 2013p2-q016 | semicircle and shaded segment | `.../2013p2-q016-b1` | `.../2013p2-q016-b2-reviewed` |
| 2013p2-q020 | bearing diagram and axis labels | `.../2013p2-q020-b1` | `.../2013p2-q020-b2-reviewed` |
| 2014p2-q016 | square, external triangle and angle mark | `.../2014p2-q016-b1` | `.../2014p2-q016-b2-reviewed` |
| 2021p2-q020 | square with intersecting triangles | `.../2021p2-q020-b1-v2` | `.../2021p2-q020-b2-reviewed` |

The reproducible input manifest is
`output/figure_pipeline/benchmark/benchmark-manifest.json`.

## Review policy

- `approved` means a human inspected the proposal and accepted it unchanged.
- `corrected` means a human changed text, kind, membership or order.
- The corrected sibling is the downstream gold result; the pending sibling is
  the model prediction used for measurement.
- Human review is required for every sample. Confidence never bypasses review.

For this baseline, five samples were approved unchanged and 2013p2-q020 was
corrected because `北` and `東` are compass `axis_label` values, not generic
`text`. The labels remained textually complete.

## v1 baseline results

| Metric | Result | Interpretation |
|---|---:|---|
| samples with a parseable proposal | 6/6 | strict JSON path stable |
| text-only label multiset match | 6/6 | no missing or hallucinated label text |
| exact `(text, kind)` proposal match | 5/6 | two compass kinds were wrong in one sample |
| micro `(text, kind)` precision | 32/34 = 94.1% | 2 wrong kind predictions |
| micro `(text, kind)` recall | 32/34 = 94.1% | 2 gold axis labels need correction |
| human-reviewed terminal bundles | 6/6 | 5 approved, 1 corrected |
| proposal confidence mean | 0.667 | not calibrated: two correct proposals reported `0.0` |

The current benchmark intentionally does not score sequence order as a hard
metric. Diagram reading order needs an explicit contract first; otherwise a
human may mistake a valid alphabetic grouping for an OCR error. Q18 remains a
separate corrected-order acceptance sample.

## Artifacts

- Pending B3 proposals: `output/figure_pipeline/benchmark/*-b3`
- Reviewed B3 gold bundles: `output/figure_pipeline/benchmark/*-b3-reviewed`
- Corrected labels input:
  `output/figure_pipeline/benchmark/2013p2-q020-b3-review-labels.json`

## Prompt iteration results

The same six reviewed B2 inputs were rerun without changing any crop. Matching
uses label multisets and `(text, kind)` multisets; sequence order is recorded
but is not a primary correctness gate.

| Metric | v1 | v2 | v3 |
|---|---:|---:|---:|
| parseable proposal | 6/6 | 5/6 | 6/6 |
| text-only exact sample | 6/6 | 5/6 | 6/6 |
| exact `(text, kind)` sample | 5/6 | 5/6 | 6/6 |
| micro TP / FP / FN | 32 / 2 / 2 | 27 / 0 / 7 | 34 / 0 / 0 |
| micro precision | 94.1% | 100.0% | 100.0% |
| micro recall | 94.1% | 79.4% | 100.0% |
| micro F1 | 94.1% | 88.5% | 100.0% |
| mean proposal confidence | 0.667 | 0.000 (5 parsed) | 0.950 |
| human review outcome | 5 approved, 1 corrected | 5 approved, 1 corrected | 6 approved |

v2 fixed the `北`/`東` kind error, but the 2014 Q16 run degenerated into 384
exclamation marks and failed strict JSON parsing. Its five valid proposals also
reported confidence `0.0`. The failed response remains preserved in the v2
bundle and the reviewed sibling is explicitly `corrected`; it was not counted
as a model prediction.

v3 keeps the axis-label and visual scan-order rules but removes v2's local
`value or marker` adjacency instruction. It also replaces the `0.0` confidence
example with a non-zero example and defines confidence over the complete
transcription. All six proposals parsed, all 34 `(text, kind)` objects matched
the human gold multisets, and all six were approved unchanged. Uniform `0.95`
confidence is consistent with this small all-correct set but is not sufficient
evidence of general calibration.

The machine-readable comparison is
`output/figure_pipeline/benchmark/b3-prompt-comparison.json`. Crop SHA-256
metadata and recomputed on-disk hashes match across every v1, v2 and v3 pending
and reviewed bundle.

## Decision

B3-v3 is the current prompt default. Artifact schema remains `1.2` and pipeline
version remains `figure-b3-v1`; prompt revisions are recorded independently as
`figure-b3-v1`, `figure-b3-v2` or `figure-b3-v3`, and all three remain readable
and rerunnable.

1. Keep order outside the primary accuracy gate until a separate order metric
   and human annotation policy are defined.
2. Add more varied holdout samples, including non-geometry figures, the 2018
   parallelogram and the 2022
   exterior-angle diagrams, before any LoRA fine-tuning decision.
3. After that holdout passes, design B4 structured figure/table analysis as a
   separate contract.

Do not treat the vector database as training. The reviewed labels are a gold
dataset for prompt evaluation and, only after a larger holdout set exists, a
possible supervised fine-tuning dataset.
