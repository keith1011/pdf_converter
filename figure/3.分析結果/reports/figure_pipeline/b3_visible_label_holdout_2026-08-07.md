# Phase B3-v3 Expanded Holdout — 2026-08-07

## Scope

This report covers six additional Figure-line samples selected to widen the
holdout beyond the original six geometry-heavy samples. Each sample was
isolated with a manual B1 bbox from the preserved DSE question crop, then
passed through B2 semantic classification and B3-v3 visible-label OCR using
one sequential local `Qwen/Qwen3-VL-8B-Instruct` 4-bit client.

The model proposal is never ground truth. B2 and B3 proposals remained in
pending bundles until a human inspected the source crop and published a
reviewed sibling bundle. The expanded manifest is
`3.分析結果/output/figure_pipeline/benchmark/benchmark-manifest-v2.json`.

## Added samples

| Sample | B1 bbox `[x1,y1,x2,y2]` | Visual focus | Reviewed B2 classification |
|---|---:|---|---|
| 2018p2-q006 | `[700,80,1340,600]` | coordinate graph, two labelled lines | `coordinate_graph / line_segment` |
| 2018p2-q016 | `[640,95,1345,560]` | parallelogram, diagonals, vertices A–F | `geometry / quadrilateral` |
| 2018p2-q032 | `[620,180,1375,900]` | logarithmic function graph | `function_graph / other` |
| 2022p2-q014 | `[60,110,1370,350]` | non-geometry dot-pattern sequence | `illustration / other` |
| 2022p2-q019 | `[720,90,1380,650]` | triangle with exterior-angle construction | `geometry / triangle` |
| 2022p2-q024 | `[650,80,1360,620]` | coordinate graph, straight line | `coordinate_graph / line_segment` |

The B1 source crop paths are recorded in the manifest and the published
bundles preserve the question crop, figure crop, bbox, parent question ID and
SHA-256 metadata.

## B2 classification result

| Metric | Result |
|---|---:|
| Samples | 6 |
| Strictly parseable proposals | 5/6 |
| Human review | 5 approved, 1 corrected |

The 2018 Q16 response was intentionally retained as a failed audit. Its raw
JSON used `secondary_tags=["triangle"]` for a geometry proposal and returned
four evidence items, so strict B2 taxonomy validation rejected it without
coercion. Human review published the corrected
`geometry / quadrilateral` decision in
`3.分析結果/output/figure_pipeline/benchmark/2018p2-q016-b2-reviewed`;
the failed source remains unchanged. The five other proposals were approved.
The B2 dot-pattern proposal reported confidence `0.0`, which is another
reason not to interpret the confidence field as calibrated probability.

## B3-v3 label OCR result

The pending proposals are under
`3.分析結果/output/figure_pipeline/benchmark/*-b3-v3`; reviewed terminal
bundles are under `*-b3-v3-reviewed`. Human inspection approved all six
proposals unchanged. For measurement, proposal labels were compared to the
reviewed labels as multisets; sequence position was deliberately not scored.

| Metric | Added holdout |
|---|---:|
| Samples with parseable proposal | 6/6 |
| Text-only exact sample match | 6/6 |
| Exact `(text, kind)` sample match | 6/6 |
| Micro TP / FP / FN | 28 / 0 / 0 |
| Micro precision / recall / F1 | 100% / 100% / 100% |
| Mean proposal confidence | 0.95 |
| Human review outcome | 6 approved unchanged |

The 28 labels are distributed as 5, 6, 8, 0, 5 and 4 across the six samples
in manifest order. The 2022 Q14 dot-pattern is a valid zero-label case: no
printed text or symbol label is visible in the crop, so the empty proposal is
not counted as a positive label.

For context, combining the original six-sample v3 benchmark with this
holdout gives:

| Metric | Combined 12 samples |
|---|---:|
| Parseable proposals | 12/12 |
| Text-only exact samples | 12/12 |
| Exact `(text, kind)` samples | 12/12 |
| Micro TP / FP / FN | 62 / 0 / 0 |
| Micro precision / recall / F1 | 100% / 100% / 100% |
| Mean proposal confidence | 0.95 |

The machine-readable form of both result sets is
`3.分析結果/output/figure_pipeline/benchmark/holdout-comparison-2026-08-07.json`.

## Integrity and limitations

- The 30 new bundles (six each for B1, B2, reviewed B2, B3-v3 and reviewed
  B3-v3) passed Pydantic schema validation.
- Recomputed figure-crop SHA-256 values matched the metadata in all 30 new
  bundles; no source bundle was overwritten.
- The six-sample holdout is wider, but it is still not a statistically
  representative estimate of deployment accuracy.
- B3 confidence is uniform at `0.95` on this run and should not be treated as
  calibrated uncertainty.
- The B3 metric uses text and `(text, kind)` multisets only. In accordance with
  the current user instruction, no separate sequence-order metric was defined
  or calculated in this round.

## Decision

The B3-v3 prompt remains the current Figure-line default. The expanded holdout
is green for visible-label content and kind accuracy, while B2 demonstrates
that strict taxonomy validation still catches malformed classifications and
requires human correction. The next implementation decision can be a
separately scoped B4 structured figure/table contract; embeddings, Qdrant
ingest, retrieval and answer reasoning remain out of scope.
