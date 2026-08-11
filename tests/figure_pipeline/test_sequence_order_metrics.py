from __future__ import annotations

import pytest
from pydantic import ValidationError

from figure_pipeline.label_ocr_models import VisibleLabel
from figure_pipeline.sequence_order_metrics import (
    SequenceGoldManifest,
    aggregate_sequence_order,
    score_sequence_order,
)


def labels(*texts: str) -> list[VisibleLabel]:
    return [VisibleLabel(text=text, kind="latin_letter") for text in texts]


def test_exact_sequence_scores_all_pairs_and_lcs() -> None:
    result = score_sequence_order(labels("A", "B", "C"), labels("A", "B", "C"))

    assert result.content_match is True
    assert result.exact_sequence is True
    assert result.label_count == 3
    assert result.comparable_pairs == 3
    assert result.concordant_pairs == 3
    assert result.pairwise_accuracy == pytest.approx(1.0)
    assert result.lcs_ratio == pytest.approx(1.0)


def test_reversed_sequence_scores_zero_pairwise_and_one_third_lcs() -> None:
    result = score_sequence_order(labels("C", "B", "A"), labels("A", "B", "C"))

    assert result.content_match is True
    assert result.exact_sequence is False
    assert result.comparable_pairs == 3
    assert result.concordant_pairs == 0
    assert result.pairwise_accuracy == pytest.approx(0.0)
    assert result.lcs_ratio == pytest.approx(1 / 3)


def test_single_swap_has_two_of_three_pairs_in_order() -> None:
    result = score_sequence_order(labels("A", "C", "B"), labels("A", "B", "C"))

    assert result.exact_sequence is False
    assert result.comparable_pairs == 3
    assert result.concordant_pairs == 2
    assert result.pairwise_accuracy == pytest.approx(2 / 3)
    assert result.lcs_ratio == pytest.approx(2 / 3)


def test_repeated_labels_are_matched_by_occurrence_index() -> None:
    result = score_sequence_order(labels("A", "A", "B"), labels("A", "B", "A"))

    assert result.content_match is True
    assert result.comparable_pairs == 3
    assert result.concordant_pairs == 2
    assert result.pairwise_accuracy == pytest.approx(2 / 3)
    assert result.lcs_ratio == pytest.approx(2 / 3)


def test_content_mismatch_is_not_scored_as_an_order_error() -> None:
    result = score_sequence_order(labels("A", "B"), labels("A", "C"))

    assert result.content_match is False
    assert result.exact_sequence is None
    assert result.comparable_pairs == 0
    assert result.concordant_pairs == 0
    assert result.pairwise_accuracy is None
    assert result.lcs_ratio is None


@pytest.mark.parametrize("predicted,gold", [([], []), (labels("A"), labels("A"))])
def test_zero_and_one_label_sequences_are_exact_but_pairwise_trivial(
    predicted: list[VisibleLabel],
    gold: list[VisibleLabel],
) -> None:
    result = score_sequence_order(predicted, gold)

    assert result.content_match is True
    assert result.exact_sequence is True
    assert result.comparable_pairs == 0
    assert result.pairwise_accuracy is None
    assert result.lcs_ratio is None


def test_aggregate_excludes_content_mismatch_and_trivial_samples() -> None:
    scores = [
        score_sequence_order(labels("A", "B", "C"), labels("A", "B", "C")),
        score_sequence_order(labels("A", "C", "B"), labels("A", "B", "C")),
        score_sequence_order([], []),
        score_sequence_order(labels("A"), labels("B")),
    ]

    aggregate = aggregate_sequence_order(scores)

    assert aggregate.sample_count == 4
    assert aggregate.evaluable_samples == 3
    assert aggregate.content_mismatch_samples == 1
    assert aggregate.trivial_samples == 1
    assert aggregate.nontrivial_samples == 2
    assert aggregate.exact_sequence_samples == 1
    assert aggregate.exact_sequence_rate == pytest.approx(0.5)
    assert aggregate.total_comparable_pairs == 6
    assert aggregate.total_concordant_pairs == 5
    assert aggregate.micro_pairwise_accuracy == pytest.approx(5 / 6)
    assert aggregate.macro_pairwise_accuracy == pytest.approx(5 / 6)
    assert aggregate.macro_lcs_ratio == pytest.approx(5 / 6)


def test_gold_manifest_rejects_duplicate_sample_ids() -> None:
    sample = {
        "sample_id": "sample-1",
        "proposal_bundle": "sample-1-b3-v3",
        "asset_id": "asset-1",
        "source_crop_sha256": "a" * 64,
        "labels": [{"text": "A", "kind": "latin_letter"}],
    }

    with pytest.raises(ValidationError):
        SequenceGoldManifest.model_validate(
            {
                "schema_version": "figure-b3-sequence-gold-v1",
                "annotation_policy_version": "visual-scan-order-v1",
                "metric_version": "occurrence-pairwise-v1",
                "samples": [sample, sample],
            }
        )
