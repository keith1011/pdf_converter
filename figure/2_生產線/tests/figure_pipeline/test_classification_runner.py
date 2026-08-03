from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import torch
from PIL import Image

from figure_pipeline.classification_models import ClassifiedFigureAsset
from figure_pipeline.classification_prompt import FIGURE_CLASSIFICATION_PROMPT
from figure_pipeline.classification_runner import classify_bundle, classify_many
from figure_pipeline.proposal import sha256_file
from ocr_pipeline import vlm_client
from ocr_pipeline.vlm_client import QwenVlClient, VlmClient
from tests.figure_pipeline.helpers import valid_asset_dict

FIXTURES = Path(__file__).parent / "fixtures"


class FakeVlmClient:
    model_name = "Qwen/Qwen3-VL-8B-Instruct"
    load_in_4bit = True

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, Path, int]] = []

    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        assert image_path is not None
        self.calls.append((prompt, image_path, int(max_new_tokens or 0)))
        return self.response


class RawAwareVlmClient(FakeVlmClient):
    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        raise AssertionError("normalized generate() must not be used when raw is available")

    def generate_raw(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        return FakeVlmClient.generate(
            self,
            prompt,
            image_path=image_path,
            max_new_tokens=max_new_tokens,
        )


class RaisingVlmClient(FakeVlmClient):
    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        super().generate(
            prompt,
            image_path=image_path,
            max_new_tokens=max_new_tokens,
        )
        raise RuntimeError("inference failed")


def valid_response() -> str:
    return (FIXTURES / "qwen_geometry_response.txt").read_text(encoding="utf-8")


def invalid_response() -> str:
    return (FIXTURES / "qwen_invalid_response.txt").read_text(encoding="utf-8")


def snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def make_b1_bundle(base: Path, *, question: int = 18) -> Path:
    source_dir = base / f"q{question:03d}-b1"
    asset_dir = source_dir / "assets"
    asset_dir.mkdir(parents=True)

    figure_name = f"q{question:03d}_fig01.png"
    crop_path = asset_dir / figure_name
    Image.new("RGB", (16, 12), color="white").save(crop_path)
    question_path = source_dir / "question.png"
    Image.new("RGB", (24, 20), color="white").save(question_path)
    (source_dir / "audit-sidecar.bin").write_bytes(b"B1-sidecar-byte-contract")

    payload = valid_asset_dict()
    parent_question_id = f"hk-dse-2015-math-p2-q{question:03d}"
    payload["asset_id"] = f"{parent_question_id}-fig01"
    payload["parent_question_id"] = parent_question_id
    payload["source"]["crop_path"] = f"assets/{figure_name}"
    payload["source"]["sha256"] = sha256_file(crop_path)
    payload["source"]["question_crop_sha256"] = sha256_file(question_path)
    (source_dir / "figure_asset.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + chr(10),
        encoding="utf-8",
    )
    return source_dir


def test_classify_bundle_preserves_bundle_and_publishes_b2_asset(
    tmp_path: Path,
) -> None:
    source_dir = make_b1_bundle(tmp_path)
    destination = tmp_path / "q018-b2"
    source_snapshot = snapshot_tree(source_dir)
    client = FakeVlmClient(valid_response())

    asset = classify_bundle(
        source_dir,
        destination,
        client=client,
        max_new_tokens=256,
    )

    assert asset.schema_version == "1.1"
    assert asset.pipeline_version == "figure-b2-v1"
    assert asset.classification.status == "pending"
    assert asset.figure_type == "unknown"
    assert asset.source.sha256 == sha256_file(destination / "assets/q018_fig01.png")
    assert (destination / "assets/q018_fig01.png").read_bytes() == source_snapshot[
        "assets/q018_fig01.png"
    ]
    assert (destination / "question.png").read_bytes() == source_snapshot["question.png"]
    assert (destination / "audit-sidecar.bin").read_bytes() == source_snapshot["audit-sidecar.bin"]
    published = ClassifiedFigureAsset.model_validate_json(
        (destination / "figure_asset.json").read_text(encoding="utf-8")
    )
    assert published == asset
    assert snapshot_tree(source_dir) == source_snapshot
    assert not (destination / "classification_response.txt").exists()
    assert client.calls == [
        (
            FIGURE_CLASSIFICATION_PROMPT,
            source_dir / "assets/q018_fig01.png",
            256,
        )
    ]


def test_classify_bundle_prefers_unmodified_raw_generation(tmp_path: Path) -> None:
    source_dir = make_b1_bundle(tmp_path)
    destination = tmp_path / "q018-b2"
    client = RawAwareVlmClient(valid_response())

    asset = classify_bundle(source_dir, destination, client=client)

    assert asset.classification.status == "pending"
    assert len(client.calls) == 1


def test_success_renames_sibling_uuid_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_b1_bundle(tmp_path)
    destination = tmp_path / "q018-b2"
    rename_calls: list[tuple[Path, Path]] = []
    original_rename = Path.rename

    def record_rename(source: Path, target: Path) -> Path:
        rename_calls.append((source, target))
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", record_rename)

    classify_bundle(
        source_dir,
        destination,
        client=FakeVlmClient(valid_response()),
    )

    assert len(rename_calls) == 1
    stage, target = rename_calls[0]
    assert stage.parent == destination.parent
    assert re.fullmatch(r"\.q018-b2\.staging-[0-9a-f]{32}", stage.name)
    assert target == destination
    assert not stage.exists()
    assert destination.is_dir()


def test_classify_many_reuses_client_in_input_order(tmp_path: Path) -> None:
    first = make_b1_bundle(tmp_path / "first", question=18)
    second = make_b1_bundle(tmp_path / "second", question=19)
    first_destination = tmp_path / "first-b2"
    second_destination = tmp_path / "second-b2"
    client = FakeVlmClient(valid_response())

    assets = classify_many(
        [(first, first_destination), (second, second_destination)],
        client=client,
        max_new_tokens=256,
    )

    assert [asset.asset_id for asset in assets] == [
        "hk-dse-2015-math-p2-q018-fig01",
        "hk-dse-2015-math-p2-q019-fig01",
    ]
    assert [call[1] for call in client.calls] == [
        first / "assets/q018_fig01.png",
        second / "assets/q019_fig01.png",
    ]
    assert all(call[2] == 256 for call in client.calls)
    assert first_destination.is_dir()
    assert second_destination.is_dir()


def test_invalid_response_publishes_auditable_failed_classification(
    tmp_path: Path,
) -> None:
    source_dir = make_b1_bundle(tmp_path)
    destination = tmp_path / "q018-b2-failed"
    client = FakeVlmClient(invalid_response())

    asset = classify_bundle(
        source_dir,
        destination,
        client=client,
        max_new_tokens=256,
    )

    response_path = destination / "classification_response.txt"
    assert asset.classification.status == "failed"
    assert asset.classification.proposed is None
    assert asset.classification.reviewed is None
    assert asset.classification.model_id == client.model_name
    assert asset.classification.quantization == "4-bit"
    assert asset.classification.prompt_version == "figure-b2-v1"
    assert asset.classification.response_path == "classification_response.txt"
    assert asset.classification.response_sha256 == sha256_file(response_path)
    assert asset.figure_type == "unknown"
    assert response_path.read_bytes() == invalid_response().encode("utf-8")
    published = ClassifiedFigureAsset.model_validate_json(
        (destination / "figure_asset.json").read_text(encoding="utf-8")
    )
    assert published == asset


def test_hash_mismatch_fails_before_inference_without_destination(
    tmp_path: Path,
) -> None:
    source_dir = make_b1_bundle(tmp_path)
    asset_path = source_dir / "figure_asset.json"
    data = json.loads(asset_path.read_text(encoding="utf-8"))
    data["source"]["sha256"] = "c" * 64
    asset_path.write_text(json.dumps(data), encoding="utf-8")
    client = FakeVlmClient(valid_response())
    destination = tmp_path / "q018-b2"

    with pytest.raises(ValueError, match="hash"):
        classify_bundle(
            source_dir,
            destination,
            client=client,
            max_new_tokens=256,
        )

    assert client.calls == []
    assert not destination.exists()
    assert list(tmp_path.glob(".q018-b2.staging-*")) == []


@pytest.mark.parametrize("raw", ["not-json", '{"schema_version": "1.0"}'])
def test_invalid_b1_json_fails_before_inference(tmp_path: Path, raw: str) -> None:
    source_dir = make_b1_bundle(tmp_path)
    (source_dir / "figure_asset.json").write_text(raw, encoding="utf-8")
    destination = tmp_path / "q018-b2"
    client = FakeVlmClient(valid_response())

    with pytest.raises(ValueError):
        classify_bundle(source_dir, destination, client=client)

    assert client.calls == []
    assert not destination.exists()
    assert list(tmp_path.glob(".q018-b2.staging-*")) == []


def test_existing_destination_is_preserved_before_inference(tmp_path: Path) -> None:
    source_dir = make_b1_bundle(tmp_path)
    destination = tmp_path / "q018-b2"
    destination.mkdir()
    sentinel = destination / "sentinel.bin"
    sentinel.write_bytes(b"do-not-touch")
    client = FakeVlmClient(valid_response())

    with pytest.raises(FileExistsError):
        classify_bundle(source_dir, destination, client=client)

    assert client.calls == []
    assert sentinel.read_bytes() == b"do-not-touch"
    assert list(tmp_path.glob(".q018-b2.staging-*")) == []


def test_generate_error_removes_stage_and_publishes_nothing(tmp_path: Path) -> None:
    source_dir = make_b1_bundle(tmp_path)
    destination = tmp_path / "q018-b2"
    client = RaisingVlmClient(valid_response())

    with pytest.raises(RuntimeError, match="inference failed"):
        classify_bundle(source_dir, destination, client=client)

    assert not destination.exists()
    assert list(tmp_path.glob(".q018-b2.staging-*")) == []


def test_vlm_protocol_remains_generate_only() -> None:
    client = FakeVlmClient(valid_response())

    assert isinstance(client, VlmClient)
    assert "close" not in VlmClient.__dict__
    assert "generate_raw" not in VlmClient.__dict__


def test_qwen_raw_generation_disables_only_fence_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = QwenVlClient()
    client.model = object()
    client.processor = object()
    strip_flags: list[bool] = []
    monkeypatch.setattr(client, "load", lambda: None)

    def fake_run_vlm_generate(**kwargs: object) -> str:
        strip_flags.append(bool(kwargs["strip_output_fences"]))
        return "model response"

    monkeypatch.setattr(vlm_client, "run_vlm_generate", fake_run_vlm_generate)

    assert client.generate("prompt") == "model response"
    assert client.generate_raw("prompt") == "model response"
    assert strip_flags == [True, False]


def test_qwen_close_releases_model_and_processor(monkeypatch: pytest.MonkeyPatch) -> None:
    client = QwenVlClient()
    client.model = object()
    client.processor = object()
    cache_calls: list[bool] = []
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: cache_calls.append(True))

    client.close()

    assert client.model is None
    assert client.processor is None
    assert cache_calls == [True]
