from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Literal

from pydantic import Field

from .label_ocr_models import LabeledFigureAsset, VisibleLabel
from .models import StrictModel, resolve_bundle_path
from .proposal import sha256_file
from .sequence_order_metrics import (
    SequenceGoldManifest,
    SequenceOrderScore,
    aggregate_sequence_order,
    score_sequence_order,
)


class SequenceSampleReport(StrictModel):
    sample_id: str
    proposal_bundle: str
    asset_id: str
    source_crop_sha256: str
    proposal_prompt_version: str
    predicted_labels: list[VisibleLabel] = Field(max_length=64)
    gold_labels: list[VisibleLabel] = Field(max_length=64)
    content_match: bool
    label_count: int = Field(ge=0)
    exact_sequence: bool | None
    comparable_pairs: int = Field(ge=0)
    concordant_pairs: int = Field(ge=0)
    pairwise_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    lcs_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class SequenceAggregateReport(StrictModel):
    sample_count: int = Field(ge=0)
    evaluable_samples: int = Field(ge=0)
    content_mismatch_samples: int = Field(ge=0)
    trivial_samples: int = Field(ge=0)
    nontrivial_samples: int = Field(ge=0)
    exact_sequence_samples: int = Field(ge=0)
    exact_sequence_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    total_comparable_pairs: int = Field(ge=0)
    total_concordant_pairs: int = Field(ge=0)
    micro_pairwise_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    macro_pairwise_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    macro_lcs_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class SequenceOrderReport(StrictModel):
    report_version: Literal["figure-b3-sequence-order-report-v1"]
    gold_schema_version: Literal["figure-b3-sequence-gold-v1"]
    annotation_policy_version: Literal["visual-scan-order-v1"]
    metric_version: Literal["occurrence-pairwise-v1"]
    aggregate: SequenceAggregateReport
    samples: list[SequenceSampleReport]


def _load_bound_proposal(
    benchmark_root: Path,
    *,
    proposal_bundle: str,
    asset_id: str,
    source_crop_sha256: str,
) -> tuple[LabeledFigureAsset, list[VisibleLabel], str]:
    bundle_dir = benchmark_root / proposal_bundle
    asset_path = bundle_dir / "figure_asset.json"
    asset = LabeledFigureAsset.model_validate_json(asset_path.read_text(encoding="utf-8"))
    if asset.asset_id != asset_id:
        raise ValueError(f"gold asset_id does not match B3 asset: {proposal_bundle}")
    if asset.source.sha256 != source_crop_sha256:
        raise ValueError(f"gold crop hash does not match B3 asset: {proposal_bundle}")

    crop_path = resolve_bundle_path(bundle_dir, asset.source.crop_path)
    if not crop_path.is_file():
        raise FileNotFoundError(crop_path)
    if sha256_file(crop_path) != source_crop_sha256:
        raise ValueError(f"B3 figure crop hash mismatch: {proposal_bundle}")

    proposal = asset.label_ocr.proposed
    if proposal is None:
        raise ValueError(f"sequence evaluation requires a parseable B3 proposal: {proposal_bundle}")
    return asset, proposal.labels, proposal.prompt_version


def _sample_report(
    *,
    sample_id: str,
    proposal_bundle: str,
    asset_id: str,
    source_crop_sha256: str,
    proposal_prompt_version: str,
    predicted_labels: list[VisibleLabel],
    gold_labels: list[VisibleLabel],
    score: SequenceOrderScore,
) -> SequenceSampleReport:
    return SequenceSampleReport(
        sample_id=sample_id,
        proposal_bundle=proposal_bundle,
        asset_id=asset_id,
        source_crop_sha256=source_crop_sha256,
        proposal_prompt_version=proposal_prompt_version,
        predicted_labels=predicted_labels,
        gold_labels=gold_labels,
        **asdict(score),
    )


def evaluate_sequence_order(
    manifest: SequenceGoldManifest,
    benchmark_root: Path,
) -> SequenceOrderReport:
    reports: list[SequenceSampleReport] = []
    scores: list[SequenceOrderScore] = []
    for sample in manifest.samples:
        _asset, predicted, prompt_version = _load_bound_proposal(
            benchmark_root,
            proposal_bundle=sample.proposal_bundle,
            asset_id=sample.asset_id,
            source_crop_sha256=sample.source_crop_sha256,
        )
        score = score_sequence_order(predicted, sample.labels)
        scores.append(score)
        reports.append(
            _sample_report(
                sample_id=sample.sample_id,
                proposal_bundle=sample.proposal_bundle,
                asset_id=sample.asset_id,
                source_crop_sha256=sample.source_crop_sha256,
                proposal_prompt_version=prompt_version,
                predicted_labels=predicted,
                gold_labels=sample.labels,
                score=score,
            )
        )

    aggregate = SequenceAggregateReport.model_validate(
        asdict(aggregate_sequence_order(scores))
    )
    return SequenceOrderReport(
        report_version="figure-b3-sequence-order-report-v1",
        gold_schema_version=manifest.schema_version,
        annotation_policy_version=manifest.annotation_policy_version,
        metric_version=manifest.metric_version,
        aggregate=aggregate,
        samples=reports,
    )
