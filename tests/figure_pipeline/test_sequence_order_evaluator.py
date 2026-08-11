from __future__ import annotations

import json
from pathlib import Path

import pytest

from figure_pipeline.sequence_order_cli import main
from figure_pipeline.sequence_order_evaluator import evaluate_sequence_order
from figure_pipeline.sequence_order_metrics import SequenceGoldManifest
from tests.figure_pipeline.test_label_ocr_review import make_pending_b3_bundle
from tests.figure_pipeline.test_label_ocr_runner import load_b3


def make_manifest(bundle: Path, *, crop_sha256: str | None = None) -> SequenceGoldManifest:
    asset = load_b3(bundle)
    proposal = asset.label_ocr.proposed
    assert proposal is not None
    return SequenceGoldManifest.model_validate(
        {
            "schema_version": "figure-b3-sequence-gold-v1",
            "annotation_policy_version": "visual-scan-order-v1",
            "metric_version": "occurrence-pairwise-v1",
            "samples": [
                {
                    "sample_id": "sample-1",
                    "proposal_bundle": bundle.name,
                    "asset_id": asset.asset_id,
                    "source_crop_sha256": crop_sha256 or asset.source.sha256,
                    "labels": [label.model_dump(mode="json") for label in proposal.labels],
                }
            ],
        }
    )


def test_evaluator_binds_gold_to_asset_and_crop_hash(tmp_path: Path) -> None:
    bundle = make_pending_b3_bundle(tmp_path)
    report = evaluate_sequence_order(make_manifest(bundle), tmp_path)

    assert report.report_version == "figure-b3-sequence-order-report-v1"
    assert report.aggregate.sample_count == 1
    assert report.aggregate.evaluable_samples == 1
    assert report.aggregate.exact_sequence_rate == pytest.approx(1.0)
    assert report.aggregate.micro_pairwise_accuracy == pytest.approx(1.0)
    assert report.samples[0].sample_id == "sample-1"
    assert report.samples[0].exact_sequence is True


def test_evaluator_rejects_gold_bound_to_the_wrong_crop(tmp_path: Path) -> None:
    bundle = make_pending_b3_bundle(tmp_path)

    with pytest.raises(ValueError, match="gold crop hash"):
        evaluate_sequence_order(make_manifest(bundle, crop_sha256="f" * 64), tmp_path)


def test_cli_writes_machine_readable_report_without_overwrite(tmp_path: Path) -> None:
    bundle = make_pending_b3_bundle(tmp_path)
    manifest_path = tmp_path / "gold.json"
    manifest_path.write_text(
        json.dumps(make_manifest(bundle).model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )
    output_path = tmp_path / "sequence-report.json"

    assert (
        main(
            [
                "--gold",
                str(manifest_path),
                "--benchmark-root",
                str(tmp_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["aggregate"]["micro_pairwise_accuracy"] == pytest.approx(1.0)

    with pytest.raises(FileExistsError):
        main(
            [
                "--gold",
                str(manifest_path),
                "--benchmark-root",
                str(tmp_path),
                "--out",
                str(output_path),
            ]
        )
