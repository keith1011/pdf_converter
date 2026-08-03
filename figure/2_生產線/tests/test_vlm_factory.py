"""VLM factory builds the locked Qwen backend without loading weights."""

from __future__ import annotations

import pytest

from ocr_pipeline.vlm_client import QwenVlClient, build_vlm_client


def test_default_backend_is_qwen_when_vlm_block_present():
    client = build_vlm_client(
        {
            "vlm": {
                "backend": "qwen",
                "model_name": "Qwen/Qwen3-VL-8B-Instruct",
                "load_in_4bit": True,
            }
        }
    )
    assert isinstance(client, QwenVlClient)
    assert client.model_name == "Qwen/Qwen3-VL-8B-Instruct"
    assert client.load_in_4bit is True


def test_qwen25_model_name_still_builds_qwen_client():
    client = build_vlm_client(
        {
            "vlm": {
                "backend": "qwen",
                "model_name": "Qwen/Qwen2.5-VL-7B-Instruct",
            }
        }
    )
    assert isinstance(client, QwenVlClient)
    assert "Qwen2.5-VL" in client.model_name


def test_build_vlm_client_default_model_is_qwen3():
    client = build_vlm_client({"vlm": {"backend": "qwen"}})
    assert isinstance(client, QwenVlClient)
    assert client.model_name == "Qwen/Qwen3-VL-8B-Instruct"


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError, match="Unknown VLM backend"):
        build_vlm_client({"vlm": {"backend": "unknown"}})
