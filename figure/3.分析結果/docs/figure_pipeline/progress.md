# Figure / Table Track B Progress

## 2026-07-31 — Phase B1 Asset Preservation

Status: implementation and one human-confirmed sample are complete.

### Scope delivered

- Added an isolated `2_生產線/src/figure_pipeline/` package; Track A OCR behavior remains
  unchanged.
- Added strict Phase B1 `FigureAsset`, source, provenance and proposal schemas.
- Added a read-only MinerU `PP-DocLayoutV2` figure proposal adapter.
- Added atomic proposal and final asset publication with no-overwrite behavior.
- Added manual bbox fallback using the same `FigureAsset` schema.
- Added a CLI at `2_生產線/_script/phase_b1_figure_asset.py`.

Phase B1 does not perform captions, classification, visible-label OCR, structured
geometry analysis, embeddings, Qdrant mutation or answer reasoning.

### Accepted sample

- Source document: `1_收集資料/data/sources/2015p2.pdf`
- Question: `hk-dse-2015-math-p2-q018`
- Page: `6`
- Upstream question crop:
  `1_收集資料/data/pdf_pages/2015p2/crops/p006_q018.png`
- MinerU detector: `mineru_pp_doclayout_v2`
- Human-confirmed candidate: `0`
- Figure bbox: `[678, 382, 1278, 735]`
- Bbox coordinate space: `question_crop_pixels`
- Asset ID: `hk-dse-2015-math-p2-q018-fig01`
- Proposal:
  `3.分析結果/output/figure_pipeline/2015p2/q018-proposal/proposal.json`
- Final asset JSON:
  `3.分析結果/output/figure_pipeline/2015p2/q018/figure_asset.json`
- Preserved question crop:
  `3.分析結果/output/figure_pipeline/2015p2/q018/question.png`
- Figure crop:
  `3.分析結果/output/figure_pipeline/2015p2/q018/assets/q018_fig01.png`

### Verification evidence

- Question crop SHA-256:
  `4f69cfa63828e86331545c9c912d1335bf884d63120d20c8bdf1fd4b0315341a`
- Figure crop SHA-256:
  `c7e9843ee365b7413cd6f2866dabc11688bd52b6f2bb8dba73eb3e264de84342`
- Both hashes were recomputed from the published files and matched
  `figure_asset.json`.
- `text_result.question_id == figure_result.parent_question_id` linkage is
  represented by the preserved parent ID
  `hk-dse-2015-math-p2-q018`.
- Figure unit suite: `19 passed`.
- Ruff: all checks passed.
- `py_compile`: exit code `0`.
- Track A aggregate SHA-256 before and after implementation:
  `4223E52BFFD7BD1A8F97C6A85F5EAC1AB6B48CCEF3D00F560853D86DB3F908E2`.

### Next phase

Phase B2 is asset classification. It must begin only after a separate scope and
acceptance design is approved.

## 2026-08-02 — Phase B2 Qwen semantic classification

Status: implemented and verified on the recorded-response fixture and the Q18
acceptance sample.

Runtime contract: local Qwen/Qwen3-VL-8B-Instruct, 4-bit, sequential client
reuse; B2 assets use schema_version=1.1 and pipeline_version=figure-b2-v1.
classification.proposed remains pending until an explicit human review command
publishes classification.reviewed; failed audits remain unresolved until a
corrected/rejected review; B1 bundles remain immutable.

CLI:

- uv run python 2_生產線/_script/phase_b2_figure_classify.py propose --asset <b1-bundle> --out <b2-bundle>
- uv run python 2_生產線/_script/phase_b2_figure_classify.py review --asset <pending-or-failed-b2> --out <reviewed-b2> --reviewer <name> --status approved|corrected|rejected

Verification: Figure pipeline suite 106 passed, B2 review/CLI targeted suite
30 passed, recorded-response Q18 acceptance passed, Ruff and git diff --check
clean. The recorded Q18 proposal preserves the original asset identity, bbox
and crop SHA-256.

Real local Qwen smoke: 3.分析結果/output/figure_pipeline/2015p2/q018-b2 was published as
a failed classification audit because the raw response contained four evidence
items and used subtype quadrilateral as a secondary tag. The strict parser
rejected it without coercion, retained the raw response and response SHA-256,
and preserved the B1 source/crop hash. On 2026-08-04, the Figure agent
reviewed the crop and published
`3.分析結果/output/figure_pipeline/2015p2/q018-b2-reviewed` as a corrected
`geometry/triangle` classification with no secondary tags. The failed source
bundle remains unchanged, and the question/figure/raw-response SHA-256 values
match the reviewed copy.

Next phase: B3 visible-label OCR. Out of scope until then: B4 structured
figure/table analysis, embeddings, Qdrant ingest and answer reasoning.

## 2026-08-05 — Phase B3 visible-label OCR

Status: implementation, automated verification and one real Q18 local-model
acceptance are complete.

Runtime contract: local `Qwen/Qwen3-VL-8B-Instruct`, 4-bit, crop-only label
transcription, sequential client reuse. B3 assets use `schema_version=1.2` and
`pipeline_version=figure-b3-v1`. The strict response contract contains only a
typed `labels` array, numeric `confidence`, and `needs_review=true`; accepted
labels are not copied into top-level `visible_labels` until explicit review.

CLI:

- `uv run python 2_生產線/_script/phase_b3_visible_labels.py propose --asset <b2-bundle> --out <b3-bundle>`
- `uv run python 2_生產線/_script/phase_b3_visible_labels.py review --asset <pending-or-failed-b3> --out <reviewed-b3> --reviewer <name> --status approved|corrected|rejected [--labels-json <corrected-labels.json>]`

Verification: B3 targeted suite `50 passed`, full Figure pipeline suite
`156 passed`, and Ruff clean. Runner/review tests cover source and crop
immutability, B2/raw-response hash validation, strict parse failure audit,
atomic no-overwrite publication, failed-source correction, and model-free
review. Q18's reviewed B2 source remains unchanged; visual inspection gives the
expected printed labels `B, β, C, A, α, D`.

Real local Qwen smoke: after the text-track PaddleOCR-VL worker released the
GPU, `3.分析結果/output/figure_pipeline/2015p2/q018-b3` was published as a valid
pending proposal. Qwen detected all six labels but ordered them
`A, B, C, D, α, β` and assigned confidence `0.0`. The crop was reviewed and a
corrected result was published at
`3.分析結果/output/figure_pipeline/2015p2/q018-b3-reviewed` with labels
`B, β, C, A, α, D`. The pending proposal remains unchanged. Question, figure
crop and inherited B2 raw-response SHA-256 values match across the B2 source,
pending B3 and reviewed B3 bundles.

Next phase: separately design B4 structured figure/table analysis. Embeddings,
Qdrant ingest and answer reasoning remain out of scope.

## 2026-08-05 — Phase B3 multi-shape benchmark

Six additional crops were processed through B1 manual figure isolation, B2
classification and real local B3 Qwen OCR: 2012 Q16/Q20, 2013 Q16/Q20, 2014
Q16 and 2021 Q20. The benchmark manifest is
`3.分析結果/output/figure_pipeline/benchmark/benchmark-manifest.json`; the
report is
`3.分析結果/reports/figure_pipeline/b3_visible_label_benchmark_2026-08-05.md`.

All six proposals parsed and found the complete text label multiset. Five were
approved unchanged; 2013 Q20 was corrected from generic `text` to
`axis_label` for `北` and `東`. Text-only match was 6/6; exact `(text, kind)`
match was 5/6 with micro precision/recall 32/34 = 94.1%. Confidence was not
calibrated: two content-correct proposals returned 0.0.

That B3 prompt iteration is recorded below. B4 structured analysis, embeddings,
Qdrant ingest and answer reasoning remain out of scope until the wider holdout
is complete.

## 2026-08-05 — Phase B3 prompt v2/v3 iteration

Prompt revisions are now independent of the stable B3 artifact contract. The
artifact remains `schema_version=1.2` and `pipeline_version=figure-b3-v1`.
Legacy `figure-b3-v1` and exploratory `figure-b3-v2` prompts remain supported;
new config defaults to `figure-b3-v3`.

The same six crops were rerun for both revisions. v2 fixed `北` and `東` as
`axis_label`, but 2014 Q16 degenerated into 384 exclamation marks and failed
strict parsing. Its metrics were 5/6 parseable and typed-exact, TP/FP/FN
27/0/7, micro F1 88.5%, with mean confidence 0.0 over parsed proposals. Human
review produced 5 approved and 1 corrected terminal bundle.

v3 removed the risky local marker-adjacency instruction and changed the
confidence anchor/policy. It achieved 6/6 parseable, text-exact and typed-exact
samples, TP/FP/FN 34/0/0, micro precision/recall/F1 100%, and 6 approved
unchanged reviews. All six proposals reported confidence 0.95; this small
all-correct set does not establish general calibration. Sequence order remains
outside the primary correctness gate.

Verification after implementation: B3 targeted suite `59 passed`, full Figure
pipeline suite `171 passed`, and Ruff clean. Recomputed crop hashes match
metadata across all v1/v2/v3 pending and reviewed bundles. Comparison report:
`3.分析結果/reports/figure_pipeline/b3_visible_label_benchmark_2026-08-05.md`;
machine-readable metrics:
`3.分析結果/output/figure_pipeline/benchmark/b3-prompt-comparison.json`.

The next holdout is now complete. A separate sequence-order metric was
intentionally not defined or scored in this round.

## 2026-08-07 — Expanded B3-v3 holdout

Six new B1 manual figure bundles were added from the 2018 and 2022 crops:

- 2018 Q6: coordinate graph with two labelled lines;
- 2018 Q16: parallelogram with diagonals and vertices A–F;
- 2018 Q32: logarithmic function graph;
- 2022 Q14: non-geometry dot-pattern sequence;
- 2022 Q19: triangle with an exterior-angle construction;
- 2022 Q24: coordinate graph with a straight line.

The expanded manifest is
`3.分析結果/output/figure_pipeline/benchmark/benchmark-manifest-v2.json` and
the machine-readable result is
`3.分析結果/output/figure_pipeline/benchmark/holdout-comparison-2026-08-07.json`.

B2 used one sequential local `Qwen/Qwen3-VL-8B-Instruct` 4-bit client. Five
of six proposals parsed. The 2018 Q16 response was retained as a failed audit
because its `secondary_tags` contained an invalid `triangle` taxonomy value and
it returned four evidence items; a human then published a corrected
`geometry/quadrilateral` review. The other five classifications were approved.

B3-v3 parsed all six proposals. Human inspection approved all six unchanged;
the new set contains 28 typed visible labels (the dot-pattern sample has zero
printed labels). Text-only and exact `(text, kind)` multiset matches are both
6/6, with TP/FP/FN `28/0/0`, precision/recall/F1 `100%`, and mean proposal
confidence `0.95`. Across the original six plus this holdout: 12/12 parseable,
62/0/0, 100% precision/recall/F1, and 12/12 exact samples. The uniform
confidence is still not a calibration claim.

The 30 new stage bundles (B1, B2, reviewed B2, B3-v3 and reviewed B3-v3) were
schema-validated and their figure-crop SHA-256 values recomputed successfully.
No source bundle was overwritten. Sequence order remains unscored by explicit
request; only label multisets are reported here. B4 structured figure/table
analysis, embeddings, Qdrant ingest and answer reasoning remain out of scope.

## 2026-08-07 — Separate B3 sequence-order metric

Sequence order is now evaluated by a separate, versioned contract rather than
by the B3 content review. `occurrence-pairwise-v1` first requires an exact typed
label multiset; content-mismatch samples are reported but excluded from order
scoring. Its primary aggregate is micro Pairwise Order Accuracy. Exact Sequence
Rate, macro Pairwise Order Accuracy and macro LCS ratio are secondary metrics.
Zero- and one-label samples are marked trivial and add no comparable pairs.

The independent `visual-scan-order-v1` gold is bound to each B3 asset ID and
figure-crop SHA-256. It scans top-to-bottom by visual band and left-to-right
within a band, anchors point labels to their labelled points, preserves repeated
occurrences and does not use alphabetical or geometry-traversal order. Existing
B3 reviewed bundles were not changed because their earlier approval did not
score sequence order.

On the twelve B3-v3 samples, all 12 typed multisets match gold; 11 samples are
nontrivial and one zero-label dot pattern is excluded from pair denominators.
Exact sequence rate is `3/11 = 27.3%`; micro Pairwise Order Accuracy is
`100/156 = 64.1%`; macro Pairwise Order Accuracy is `64.8%`; macro LCS ratio is
`69.4%`. Content accuracy therefore remains 100%, but visual order does not.

Definition:
`3.分析結果/docs/figure_pipeline/sequence_order_metric_v1.md`; gold:
`3.分析結果/evals/figure_pipeline/b3_sequence_order_gold_v1.json`; result:
`3.分析結果/output/figure_pipeline/benchmark/b3-sequence-order-v1.json`;
report:
`3.分析結果/reports/figure_pipeline/b3_sequence_order_evaluation_2026-08-07.md`.

The evaluator has targeted unit and CLI coverage. Before using this metric as
a release gate, obtain a second independent annotation and measure agreement
on ambiguous row grouping. Full Figure suite: `183 passed`; Ruff clean. No B3
prompt or reviewed artifact was modified.
