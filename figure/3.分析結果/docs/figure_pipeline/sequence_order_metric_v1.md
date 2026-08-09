# Figure B3 Sequence-order Metric v1

## Purpose

This metric evaluates only the order of B3 visible-label tokens. It is kept
separate from text and `(text, kind)` accuracy so a missing, hallucinated or
mistyped label is not counted again as an ordering error.

Contract versions:

- gold schema: `figure-b3-sequence-gold-v1`;
- annotation policy: `visual-scan-order-v1`;
- metric: `occurrence-pairwise-v1`;
- report: `figure-b3-sequence-order-report-v1`.

## Gold annotation policy

1. Annotate from the preserved figure crop. Do not use alphabetical order,
   geometry traversal order, legend/category grouping or inferred semantics.
2. Use visual scan order: top-to-bottom across visual bands, then left-to-right
   inside an obvious horizontal band.
3. A point or vertex label is anchored to its labelled point when that point is
   unambiguous. Other labels use the centre of the printed label. This keeps
   labels such as `B, E, C` on one geometric baseline even when glyph baselines
   differ slightly.
4. A printed local expression such as `y = log_a x` remains one B3 token. Its
   internal character order is outside this metric.
5. Preserve repeated visible occurrences. Repeated identical `(text, kind)`
   tokens are assigned stable occurrence indices in appearance order.
6. Bind every gold sample to `asset_id` and figure-crop SHA-256. A hash or asset
   mismatch invalidates the evaluation instead of silently reusing the gold.

The v1 gold file is
`3.分析結果/evals/figure_pipeline/b3_sequence_order_gold_v1.json`. It is
independent of the earlier B3 reviewed bundles because those reviews explicitly
did not use order as an acceptance condition.

## Eligibility

Let `P` be the predicted ordered list of typed `(text, kind)` labels and `G`
the ordered gold list.

- If `multiset(P) != multiset(G)`, the sample is `content_mismatch` and is not
  assigned an order score.
- If the typed multisets match, the sample is order-evaluable.
- A gold sequence with fewer than two labels is `trivial`: exact equality may
  be recorded, but it contributes no comparable pair and is excluded from
  pairwise, exact-sequence-rate and LCS aggregate denominators.

## Primary metric: Pairwise Order Accuracy

For an evaluable sequence of `n >= 2` occurrence-aware tokens, compare every
unordered token pair. A pair is concordant when the prediction preserves the
same relative order as gold.

```text
POA(sample) = concordant_pairs / (n choose 2)

micro_POA = sum(concordant_pairs) / sum(comparable_pairs)
```

`micro_POA` is the primary aggregate because it weights each label pair equally
and does not let small diagrams dominate the result. `macro_POA`, the arithmetic
mean of nontrivial sample POA values, is reported as a secondary view.

## Secondary metrics

- `Exact Sequence Rate`: fraction of nontrivial evaluable samples whose entire
  occurrence-aware sequence exactly equals gold.
- `LCS ratio`: longest common subsequence length divided by gold label count.
  The report uses the macro mean over nontrivial evaluable samples.
- `content_mismatch_samples` and `trivial_samples` are always reported beside
  order metrics so exclusions are visible.

## Reproducible command

```powershell
uv run python 2_生產線/_script/evaluate_b3_sequence_order.py `
  --gold 3.分析結果/evals/figure_pipeline/b3_sequence_order_gold_v1.json `
  --benchmark-root 3.分析結果/output/figure_pipeline/benchmark `
  --out 3.分析結果/output/figure_pipeline/benchmark/b3-sequence-order-v1.json
```

The output path is no-overwrite. Use a new report filename for a new model,
prompt, gold revision or rerun that must be preserved.

## Interpretation boundary

The metric measures agreement with one explicit scan-order policy, not the only
possible human reading order. The current gold has one annotation pass. Before
turning POA into a release threshold, add a second independent annotation and
measure inter-annotator agreement on ambiguous row grouping.
