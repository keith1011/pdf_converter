from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_wheel_includes_both_runtime_packages() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/ocr_pipeline",
        "src/figure_pipeline",
    ]


def test_figure_config_preserves_locked_ocr_contract() -> None:
    config = yaml.safe_load(
        (ROOT / "config/ocr_pipeline.yaml").read_text(encoding="utf-8")
    )

    assert config["engines"]["text"] == "paddleocr_vl"
    assert config["pipeline"]["mcq_stage3"] == "sanitize"
    assert config["nup"]["enabled"] is False
    assert config["structured_ocr"]["enabled"] is False
    assert config["figure_classification"] == {
        "enabled": True,
        "max_new_tokens": 256,
        "prompt_version": "figure-b2-v1",
    }
    assert config["figure_label_ocr"] == {
        "enabled": True,
        "max_new_tokens": 384,
        "prompt_version": "figure-b3-v3",
    }
