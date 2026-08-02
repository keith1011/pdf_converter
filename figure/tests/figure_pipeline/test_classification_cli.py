from __future__ import annotations

from pathlib import Path

import figure_pipeline.classification_cli as cli_module
import pytest
from figure_pipeline.classification_cli import main

from tests.figure_pipeline.test_classification_review import (
    load_asset,
    make_pending_b2_bundle,
    proposal_id,
)
from tests.figure_pipeline.test_classification_runner import (
    make_b1_bundle,
    valid_response,
)


class FakeVlmClient:
    model_name = "Qwen/Qwen3-VL-8B-Instruct"
    load_in_4bit = True

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, Path, int]] = []
        self.close_calls = 0

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

    def close(self) -> None:
        self.close_calls += 1


def install_propose_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeVlmClient,
    config: dict[str, object],
) -> tuple[list[Path | None], list[dict[str, object] | None]]:
    load_calls: list[Path | None] = []
    build_calls: list[dict[str, object] | None] = []

    def load_config(path: Path | None = None) -> dict[str, object]:
        load_calls.append(path)
        return config

    def build_client(cfg: dict[str, object] | None = None) -> FakeVlmClient:
        build_calls.append(cfg)
        return fake

    monkeypatch.setattr(cli_module, "load_ocr_config", load_config)
    monkeypatch.setattr(cli_module, "build_vlm_client", build_client)
    return load_calls, build_calls


def test_cli_propose_wires_configured_client_token_budget_and_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_b1_bundle(tmp_path)
    destination = tmp_path / "cli-b2"
    config_path = tmp_path / "custom-ocr.yaml"
    config: dict[str, object] = {
        "vlm": {"backend": "qwen"},
        "figure_classification": {
            "max_new_tokens": 256,
            "prompt_version": "figure-b2-v1",
        },
    }
    fake = FakeVlmClient(valid_response())
    load_calls, build_calls = install_propose_dependencies(
        monkeypatch,
        fake,
        config,
    )

    exit_code = main(
        [
            "propose",
            "--asset",
            str(source_dir),
            "--out",
            str(destination),
            "--config",
            str(config_path),
        ]
    )

    assert exit_code == 0
    assert load_calls == [config_path]
    assert build_calls == [config]
    assert len(fake.calls) == 1
    assert fake.calls[0][2] == 256
    assert fake.close_calls == 1
    published = load_asset(destination)
    assert published.classification.proposed is not None
    assert published.classification.proposed.prompt_version == "figure-b2-v1"


def test_cli_propose_closes_client_when_classification_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_b1_bundle(tmp_path)
    (source_dir / "assets/q018_fig01.png").write_bytes(b"tampered")
    destination = tmp_path / "cli-b2"
    config: dict[str, object] = {
        "figure_classification": {
            "max_new_tokens": 256,
            "prompt_version": "figure-b2-v1",
        }
    }
    fake = FakeVlmClient(valid_response())
    install_propose_dependencies(monkeypatch, fake, config)

    with pytest.raises(ValueError, match="hash"):
        main(
            [
                "propose",
                "--asset",
                str(source_dir),
                "--out",
                str(destination),
            ]
        )

    assert fake.calls == []
    assert fake.close_calls == 1
    assert not destination.exists()


def test_cli_rejected_review_skips_model_and_uses_unknown_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    destination = tmp_path / "rejected"

    def fail_if_model_is_built(cfg: dict[str, object] | None = None) -> None:
        raise AssertionError(f"review must not build a model: {cfg}")

    monkeypatch.setattr(cli_module, "build_vlm_client", fail_if_model_is_built)

    exit_code = main(
        [
            "review",
            "--asset",
            str(source_dir),
            "--out",
            str(destination),
            "--reviewer",
            "human-1",
            "--status",
            "rejected",
        ]
    )

    assert exit_code == 0
    asset = load_asset(destination)
    reviewed = asset.classification.reviewed
    assert reviewed is not None
    assert reviewed.visual_family == "unknown"
    assert reviewed.subtype == "unclassified"
    assert reviewed.secondary_tags == []
    assert reviewed.source_proposal_id == proposal_id(source_dir)
    assert asset.figure_type == "unknown"


@pytest.mark.parametrize("status", ["approved", "corrected"])
@pytest.mark.parametrize(
    ("present_label", "missing_flag"),
    [
        (["--subtype", "triangle"], "--visual-family"),
        (["--visual-family", "geometry"], "--subtype"),
    ],
)
def test_cli_approved_and_corrected_reviews_require_both_labels(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    status: str,
    present_label: list[str],
    missing_flag: str,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "review",
                "--asset",
                str(tmp_path / "pending"),
                "--out",
                str(tmp_path / "reviewed"),
                "--reviewer",
                "human-2",
                "--status",
                status,
                *present_label,
            ]
        )

    assert exc_info.value.code == 2
    assert missing_flag in capsys.readouterr().err


@pytest.mark.parametrize(
    ("label_args", "rejected_flag"),
    [
        (["--visual-family", "geometry"], "--visual-family"),
        (["--subtype", "triangle"], "--subtype"),
    ],
)
def test_cli_rejected_review_rejects_explicit_labels(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    label_args: list[str],
    rejected_flag: str,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "review",
                "--asset",
                str(tmp_path / "pending"),
                "--out",
                str(tmp_path / "reviewed"),
                "--reviewer",
                "human-3",
                "--status",
                "rejected",
                *label_args,
            ]
        )

    assert exc_info.value.code == 2
    error = capsys.readouterr().err
    assert "rejected" in error
    assert rejected_flag in error


def test_cli_review_preserves_repeated_secondary_tags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_pending_b2_bundle(tmp_path)
    destination = tmp_path / "corrected"

    def fail_if_model_is_built(cfg: dict[str, object] | None = None) -> None:
        raise AssertionError(f"review must not build a model: {cfg}")

    monkeypatch.setattr(cli_module, "build_vlm_client", fail_if_model_is_built)

    exit_code = main(
        [
            "review",
            "--asset",
            str(source_dir),
            "--out",
            str(destination),
            "--reviewer",
            "human-4",
            "--status",
            "corrected",
            "--visual-family",
            "coordinate_graph",
            "--subtype",
            "point_plot",
            "--secondary-tag",
            "geometry",
            "--secondary-tag",
            "table",
        ]
    )

    assert exit_code == 0
    asset = load_asset(destination)
    reviewed = asset.classification.reviewed
    assert reviewed is not None
    assert reviewed.secondary_tags == ["geometry", "table"]
