from __future__ import annotations

import json
from pathlib import Path

import pytest

import figure_pipeline.label_ocr_cli as cli_module
import figure_pipeline.label_ocr_prompt as prompt_module
from figure_pipeline.label_ocr_cli import main
from tests.figure_pipeline.test_classification_review import make_approved_b2_bundle
from tests.figure_pipeline.test_label_ocr_review import make_pending_b3_bundle
from tests.figure_pipeline.test_label_ocr_runner import VALID_RAW, FakeVlmClient, load_b3


def test_cli_propose_wires_config_client_budget_and_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_approved_b2_bundle(tmp_path)
    destination = tmp_path / "cli-b3"
    config_path = tmp_path / "ocr.yaml"
    config: dict[str, object] = {
        "figure_label_ocr": {
            "max_new_tokens": 448,
            "prompt_version": "figure-b3-v1",
        }
    }
    fake = FakeVlmClient(VALID_RAW)
    fake.close_calls = 0

    def close() -> None:
        fake.close_calls += 1

    fake.close = close
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
    assert fake.calls[0][2] == 448
    assert fake.close_calls == 1


@pytest.mark.parametrize(
    ("configured_prompt_version", "expected_prompt_version"),
    [
        (None, "figure-b3-v3"),
        ("figure-b3-v1", "figure-b3-v1"),
        ("figure-b3-v2", "figure-b3-v2"),
        ("figure-b3-v3", "figure-b3-v3"),
    ],
)
def test_cli_propose_selects_current_default_or_configured_b3_prompt_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_prompt_version: str | None,
    expected_prompt_version: str,
) -> None:
    source_dir = make_approved_b2_bundle(tmp_path)
    config: dict[str, object] = {"figure_label_ocr": {}}
    if configured_prompt_version is not None:
        config["figure_label_ocr"] = {"prompt_version": configured_prompt_version}
    fake = FakeVlmClient(VALID_RAW)

    monkeypatch.setattr(cli_module, "load_ocr_config", lambda path=None: config)
    monkeypatch.setattr(cli_module, "build_vlm_client", lambda cfg=None: fake)

    assert (
        main(
            [
                "propose",
                "--asset",
                str(source_dir),
                "--out",
                str(tmp_path / f"cli-{expected_prompt_version}"),
            ]
        )
        == 0
    )
    resolver = getattr(prompt_module, "get_visible_label_prompt", None)
    assert callable(resolver), "B3 prompt versions require get_visible_label_prompt()"
    assert fake.calls[0][0] == resolver(expected_prompt_version)


def test_cli_approved_review_skips_model_and_uses_proposal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = make_pending_b3_bundle(tmp_path)
    destination = tmp_path / "approved"

    def fail_if_model_is_built(cfg: dict[str, object] | None = None) -> None:
        raise AssertionError(f"review must not build a model: {cfg}")

    monkeypatch.setattr(cli_module, "build_vlm_client", fail_if_model_is_built)

    assert (
        main(
            [
                "review",
                "--asset",
                str(source_dir),
                "--out",
                str(destination),
                "--reviewer",
                "human-b3",
                "--status",
                "approved",
            ]
        )
        == 0
    )
    asset = load_b3(destination)
    assert asset.label_ocr.status == "approved"
    assert asset.label_ocr.proposed is not None
    assert asset.visible_labels == asset.label_ocr.proposed.labels


def test_cli_corrected_review_loads_explicit_labels_json(tmp_path: Path) -> None:
    source_dir = make_pending_b3_bundle(tmp_path)
    destination = tmp_path / "corrected"
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            [
                {"text": "A", "kind": "latin_letter"},
                {"text": "α", "kind": "greek_letter"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "review",
                "--asset",
                str(source_dir),
                "--out",
                str(destination),
                "--reviewer",
                "human-b3",
                "--status",
                "corrected",
                "--labels-json",
                str(labels_path),
            ]
        )
        == 0
    )
    asset = load_b3(destination)
    assert [(label.text, label.kind) for label in asset.visible_labels] == [
        ("A", "latin_letter"),
        ("α", "greek_letter"),
    ]


def test_cli_corrected_requires_labels_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "review",
                "--asset",
                str(tmp_path / "source"),
                "--out",
                str(tmp_path / "out"),
                "--reviewer",
                "human-b3",
                "--status",
                "corrected",
            ]
        )

    assert exc_info.value.code == 2
    assert "--labels-json" in capsys.readouterr().err
