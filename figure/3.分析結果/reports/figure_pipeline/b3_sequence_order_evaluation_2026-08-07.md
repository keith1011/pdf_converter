# Phase B3-v3 Sequence-order Evaluation — 2026-08-07

## Outcome

The B3 sequence-order metric is now defined separately from label content
accuracy. All twelve v3 proposals have the correct typed label multiset and are
therefore order-evaluable. The zero-label dot-pattern sample is trivial and is
excluded from pairwise and exact-rate denominators.

| Metric | Result |
|---|---:|
| Samples | 12 |
| Content-matched / order-evaluable | 12/12 |
| Nontrivial order samples | 11 |
| Trivial samples | 1 |
| Exact ordered sequences | 3/11 = 27.3% |
| Concordant / comparable pairs | 100/156 |
| Micro Pairwise Order Accuracy | 64.1% |
| Macro Pairwise Order Accuracy | 64.8% |
| Macro LCS ratio | 69.4% |

The result is diagnostic: B3-v3 is strong at label membership and kind but does
not reliably follow the requested visual scan order. Several predictions fall
back to alphabetical or semantic grouping.

## Per-sample results

| Sample | Exact | Concordant pairs | POA | LCS ratio |
|---|---:|---:|---:|---:|
| 2012p2-q016 | yes | 10/10 | 100.0% | 100.0% |
| 2012p2-q020 | no | 15/28 | 53.6% | 62.5% |
| 2013p2-q016 | no | 1/3 | 33.3% | 66.7% |
| 2013p2-q020 | no | 7/10 | 70.0% | 80.0% |
| 2014p2-q016 | yes | 21/21 | 100.0% | 100.0% |
| 2021p2-q020 | no | 11/15 | 73.3% | 66.7% |
| 2018p2-q006 | no | 1/10 | 10.0% | 40.0% |
| 2018p2-q016 | no | 9/15 | 60.0% | 50.0% |
| 2018p2-q032 | no | 12/28 | 42.9% | 37.5% |
| 2022p2-q014 | trivial | 0/0 | n/a | n/a |
| 2022p2-q019 | no | 7/10 | 70.0% | 60.0% |
| 2022p2-q024 | yes | 6/6 | 100.0% | 100.0% |

The weakest case is 2018 Q6: the prediction begins with `L_1, L_2` and ends
with `y`, while the visual policy starts at the top `y`, then scans the `O, x`
axis row, followed by `L_2, L_1`. The logarithmic graph also groups axes and
points before its upper legend text instead of scanning globally downward.

## Metric contract and artifacts

- Definition:
  `3.分析結果/docs/figure_pipeline/sequence_order_metric_v1.md`
- Independent gold:
  `3.分析結果/evals/figure_pipeline/b3_sequence_order_gold_v1.json`
- Machine-readable result:
  `3.分析結果/output/figure_pipeline/benchmark/b3-sequence-order-v1.json`
- Evaluator CLI:
  `2_生產線/_script/evaluate_b3_sequence_order.py`

Pairwise Order Accuracy is occurrence-aware and only runs when predicted and
gold `(text, kind)` multisets match. Empty or one-label samples contribute no
pairs. The evaluator validates each bound `asset_id`, crop file and SHA-256 and
publishes the JSON report with no-overwrite behavior.

## Decision

Do not treat the previous 100% content F1 as evidence of correct reading order.
B3-v3 remains acceptable for label membership and kind, but its current order
score is 64.1% micro POA and 27.3% exact sequence rate. This evaluation does not
change the prompt or reviewed artifacts. A prompt/model improvement should be
run against the same gold as a new report, and a second independent gold
annotation is advisable before adopting a release threshold.
