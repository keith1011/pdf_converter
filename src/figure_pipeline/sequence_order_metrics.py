from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator

from .label_ocr_models import VisibleLabel
from .models import StrictModel

LabelKey = tuple[str, str]
OccurrenceKey = tuple[str, str, int]


class SequenceGoldSample(StrictModel):
    sample_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    proposal_bundle: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    asset_id: str = Field(min_length=1)
    source_crop_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    labels: list[VisibleLabel] = Field(default_factory=list, max_length=64)
    note: str | None = Field(default=None, min_length=1)


class SequenceGoldManifest(StrictModel):
    schema_version: Literal["figure-b3-sequence-gold-v1"]
    annotation_policy_version: Literal["visual-scan-order-v1"]
    metric_version: Literal["occurrence-pairwise-v1"]
    samples: list[SequenceGoldSample] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_samples(self) -> SequenceGoldManifest:
        sample_ids = [sample.sample_id for sample in self.samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("sequence gold sample_id values must be unique")
        bundles = [sample.proposal_bundle for sample in self.samples]
        if len(bundles) != len(set(bundles)):
            raise ValueError("sequence gold proposal_bundle values must be unique")
        return self


@dataclass(frozen=True)
class SequenceOrderScore:
    content_match: bool
    label_count: int
    exact_sequence: bool | None
    comparable_pairs: int
    concordant_pairs: int
    pairwise_accuracy: float | None
    lcs_ratio: float | None


@dataclass(frozen=True)
class SequenceOrderAggregate:
    sample_count: int
    evaluable_samples: int
    content_mismatch_samples: int
    trivial_samples: int
    nontrivial_samples: int
    exact_sequence_samples: int
    exact_sequence_rate: float | None
    total_comparable_pairs: int
    total_concordant_pairs: int
    micro_pairwise_accuracy: float | None
    macro_pairwise_accuracy: float | None
    macro_lcs_ratio: float | None


def _label_keys(labels: Sequence[VisibleLabel]) -> list[LabelKey]:
    return [(label.text, label.kind) for label in labels]


def _occurrence_keys(keys: Sequence[LabelKey]) -> list[OccurrenceKey]:
    counts: Counter[LabelKey] = Counter()
    result: list[OccurrenceKey] = []
    for text, kind in keys:
        base = (text, kind)
        counts[base] += 1
        result.append((text, kind, counts[base]))
    return result


def _inversion_count(positions: Sequence[int]) -> int:
    return sum(
        positions[left] > positions[right]
        for left in range(len(positions))
        for right in range(left + 1, len(positions))
    )


def _lcs_length(left: Sequence[OccurrenceKey], right: Sequence[OccurrenceKey]) -> int:
    previous = [0] * (len(right) + 1)
    for left_item in left:
        current = [0]
        for index, right_item in enumerate(right, start=1):
            if left_item == right_item:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[index - 1]))
        previous = current
    return previous[-1]


def score_sequence_order(
    predicted: Sequence[VisibleLabel],
    gold: Sequence[VisibleLabel],
) -> SequenceOrderScore:
    predicted_keys = _label_keys(predicted)
    gold_keys = _label_keys(gold)
    label_count = len(gold_keys)
    if Counter(predicted_keys) != Counter(gold_keys):
        return SequenceOrderScore(
            content_match=False,
            label_count=label_count,
            exact_sequence=None,
            comparable_pairs=0,
            concordant_pairs=0,
            pairwise_accuracy=None,
            lcs_ratio=None,
        )

    predicted_occurrences = _occurrence_keys(predicted_keys)
    gold_occurrences = _occurrence_keys(gold_keys)
    exact_sequence = predicted_occurrences == gold_occurrences
    if label_count < 2:
        return SequenceOrderScore(
            content_match=True,
            label_count=label_count,
            exact_sequence=exact_sequence,
            comparable_pairs=0,
            concordant_pairs=0,
            pairwise_accuracy=None,
            lcs_ratio=None,
        )

    gold_positions = {occurrence: index for index, occurrence in enumerate(gold_occurrences)}
    predicted_positions = [gold_positions[occurrence] for occurrence in predicted_occurrences]
    comparable_pairs = label_count * (label_count - 1) // 2
    discordant_pairs = _inversion_count(predicted_positions)
    concordant_pairs = comparable_pairs - discordant_pairs
    return SequenceOrderScore(
        content_match=True,
        label_count=label_count,
        exact_sequence=exact_sequence,
        comparable_pairs=comparable_pairs,
        concordant_pairs=concordant_pairs,
        pairwise_accuracy=concordant_pairs / comparable_pairs,
        lcs_ratio=_lcs_length(predicted_occurrences, gold_occurrences) / label_count,
    )


def aggregate_sequence_order(
    scores: Sequence[SequenceOrderScore],
) -> SequenceOrderAggregate:
    evaluable = [score for score in scores if score.content_match]
    nontrivial = [score for score in evaluable if score.label_count >= 2]
    trivial_samples = len(evaluable) - len(nontrivial)
    exact_sequence_samples = sum(score.exact_sequence is True for score in nontrivial)
    total_comparable_pairs = sum(score.comparable_pairs for score in nontrivial)
    total_concordant_pairs = sum(score.concordant_pairs for score in nontrivial)

    if nontrivial:
        exact_sequence_rate = exact_sequence_samples / len(nontrivial)
        macro_pairwise_accuracy = sum(
            score.pairwise_accuracy for score in nontrivial if score.pairwise_accuracy is not None
        ) / len(nontrivial)
        macro_lcs_ratio = sum(
            score.lcs_ratio for score in nontrivial if score.lcs_ratio is not None
        ) / len(nontrivial)
    else:
        exact_sequence_rate = None
        macro_pairwise_accuracy = None
        macro_lcs_ratio = None

    micro_pairwise_accuracy = (
        total_concordant_pairs / total_comparable_pairs
        if total_comparable_pairs
        else None
    )
    return SequenceOrderAggregate(
        sample_count=len(scores),
        evaluable_samples=len(evaluable),
        content_mismatch_samples=len(scores) - len(evaluable),
        trivial_samples=trivial_samples,
        nontrivial_samples=len(nontrivial),
        exact_sequence_samples=exact_sequence_samples,
        exact_sequence_rate=exact_sequence_rate,
        total_comparable_pairs=total_comparable_pairs,
        total_concordant_pairs=total_concordant_pairs,
        micro_pairwise_accuracy=micro_pairwise_accuracy,
        macro_pairwise_accuracy=macro_pairwise_accuracy,
        macro_lcs_ratio=macro_lcs_ratio,
    )
