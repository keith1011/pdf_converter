from __future__ import annotations

import json
from pathlib import Path

import pytest

import figure_pipeline.label_ocr_prompt as prompt_module
from figure_pipeline.classification_models import ReviewedClassification
from figure_pipeline.classification_review import review_bundle
from figure_pipeline.label_ocr_models import LabeledFigureAsset
from figure_pipeline.label_ocr_prompt import VISIBLE_LABEL_PROMPT
from figure_pipeline.label_ocr_runner import extract_visible_labels_bundle
from figure_pipeline.proposal import sha256_file
from tests.figure_pipeline.test_classification_review import (
    make_approved_b2_bundle,
    make_failed_b2_bundle,
    proposal_id,
)

FIXTURE = Path(__file__).parent / "fixtures/qwen_visible_labels_response.txt"
VALID_RAW = FIXTURE.read_text(encoding="utf-8")


def prompt_for(version: str) -> str:
    resolver = getattr(prompt_module, "get_visible_label_prompt", None)
    assert callable(resolver), "B3 prompt versions require get_visible_label_prompt()"
    return resolver(version)


class FakeVlmClient:
    model_name = "Qwen/Qwen3-VL-8B-Instruct"
    load_in_4bit = True

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, Path, int]] = []

    def generate_raw(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        assert image_path is not None
        self.calls.append((prompt, image_path, int(max_new_tokens or 0)))
        return self.response

    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        raise AssertionError("runner must prefer generate_raw when available")


def snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def load_b3(source_dir: Path) -> LabeledFigureAsset:
    return LabeledFigureAsset.model_validate_json(
        (source_dir / "figure_asset.json").read_text(encoding="utf-8")
    )


def make_corrected_failed_b2_bundle(base: Path) -> Path:
    failed = make_failed_b2_bundle(base)
    destination = base / "corrected-failed-b2"
    review_bundle(
        failed,
        destination,
        ReviewedClassification(
            visual_family="geometry",
            subtype="triangle",
            secondary_tags=[],
            status="corrected",
            reviewer="human-b2",
            source_proposal_id=proposal_id(failed),
        ),
    )
    return destination


def test_runner_publishes_pending_b3_and_preserves_whole_b2_source(
    tmp_path: Path,
) -> None:
    source_dir = make_approved_b2_bundle(tmp_path)
    destination = tmp_path / "q018-b3"
    source_snapshot = snapshot_tree(source_dir)
    client = FakeVlmClient(VALID_RAW)

    asset = extract_visible_labels_bundle(
        source_dir,
        destination,
        client=client,
        max_new_tokens=384,
    )

    assert asset.schema_version == "1.2"
    assert asset.pipeline_version == "figure-b3-v1"
    assert asset.label_ocr.status == "pending"
    assert asset.label_ocr.proposed is not None
    assert [label.text for label in asset.label_ocr.proposed.labels] == [
        "B",
        "β",
        "C",
        "A",
        "α",
        "D",
    ]
    assert asset.visible_labels == []
    assert asset.classification.status == "approved"
    assert asset.figure_type == "geometry"
    assert snapshot_tree(source_dir) == source_snapshot
    assert len(client.calls) == 1
    assert client.calls[0][0] == prompt_for("figure-b3-v3")
    assert client.calls[0][2] == 384
    assert load_b3(destination) == asset
    destination_snapshot = snapshot_tree(destination)
    for relative_path, content in source_snapshot.items():
        if relative_path != "figure_asset.json":
            assert destination_snapshot[relative_path] == content


def test_runner_uses_v3_prompt_by_default_and_keeps_v1_v2_selectable(
    tmp_path: Path,
) -> None:
    source_dir = make_approved_b2_bundle(tmp_path)
    default_client = FakeVlmClient(VALID_RAW)
    explicit_v1_client = FakeVlmClient(VALID_RAW)
    explicit_v2_client = FakeVlmClient(VALID_RAW)

    default_asset = extract_visible_labels_bundle(
        source_dir,
        tmp_path / "default-v3",
        client=default_client,
    )
    legacy_asset = extract_visible_labels_bundle(
        source_dir,
        tmp_path / "explicit-v1",
        client=explicit_v1_client,
        prompt_version="figure-b3-v1",
    )
    v2_asset = extract_visible_labels_bundle(
        source_dir,
        tmp_path / "explicit-v2",
        client=explicit_v2_client,
        prompt_version="figure-b3-v2",
    )

    assert default_asset.label_ocr.proposed is not None
    assert default_asset.label_ocr.proposed.prompt_version == "figure-b3-v3"
    assert default_client.calls[0][0] == prompt_for("figure-b3-v3")
    assert legacy_asset.label_ocr.proposed is not None
    assert legacy_asset.label_ocr.proposed.prompt_version == "figure-b3-v1"
    assert explicit_v1_client.calls[0][0] == VISIBLE_LABEL_PROMPT
    assert prompt_for("figure-b3-v1") == VISIBLE_LABEL_PROMPT
    assert v2_asset.label_ocr.proposed is not None
    assert v2_asset.label_ocr.proposed.prompt_version == "figure-b3-v2"
    assert explicit_v2_client.calls[0][0] == prompt_for("figure-b3-v2")


def test_runner_records_invalid_response_as_failed_audit(tmp_path: Path) -> None:
    source_dir = make_approved_b2_bundle(tmp_path)
    destination = tmp_path / "q018-b3-failed"
    client = FakeVlmClient("not-json")

    asset = extract_visible_labels_bundle(source_dir, destination, client=client)

    assert asset.label_ocr.status == "failed"
    assert asset.label_ocr.proposed is None
    assert asset.visible_labels == []
    response_path = destination / "visible_label_response.txt"
    assert response_path.read_text(encoding="utf-8") == "not-json"
    assert asset.label_ocr.response_sha256 == sha256_file(response_path)


def test_runner_rejects_tampered_b2_audit_before_model_call(tmp_path: Path) -> None:
    source_dir = make_corrected_failed_b2_bundle(tmp_path)
    (source_dir / "classification_response.txt").write_text(
        '{"tampered":true}',
        encoding="utf-8",
    )
    destination = tmp_path / "q018-b3"
    client = FakeVlmClient(VALID_RAW)

    with pytest.raises(ValueError, match="B2 classification response hash"):
        extract_visible_labels_bundle(source_dir, destination, client=client)

    assert client.calls == []
    assert not destination.exists()


def test_runner_rejects_existing_destination_without_mutation(tmp_path: Path) -> None:
    source_dir = make_approved_b2_bundle(tmp_path)
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "sentinel.json"
    sentinel.write_text(json.dumps({"keep": True}), encoding="utf-8")

    with pytest.raises(FileExistsError):
        extract_visible_labels_bundle(
            source_dir,
            destination,
            client=FakeVlmClient(VALID_RAW),
        )

    assert sentinel.read_text(encoding="utf-8") == '{"keep": true}'
