"""T7: VlmClient factory selects Qwen vs GLM without loading weights."""

from __future__ import annotations

from ocr_pipeline.glm_client import Glm46VFlashClient
from ocr_pipeline.vlm_client import Qwen25VlClient, build_vlm_client


def test_default_backend_is_qwen_when_vlm_block_present():
    client = build_vlm_client(
        {
            "vlm": {
                "backend": "qwen",
                "model_name": "Qwen/Qwen2.5-VL-7B-Instruct",
                "load_in_4bit": True,
            }
        }
    )
    assert isinstance(client, Qwen25VlClient)
    assert client.model_name == "Qwen/Qwen2.5-VL-7B-Instruct"
    assert client.load_in_4bit is True


def test_glm_backend_selected():
    client = build_vlm_client(
        {
            "vlm": {"backend": "glm", "model_name": "zai-org/GLM-4.6V-Flash"},
            "glm": {"model_name": "zai-org/GLM-4.6V-Flash"},
        }
    )
    assert isinstance(client, Glm46VFlashClient)


def test_legacy_glm_only_config():
    client = build_vlm_client({"glm": {"model_name": "zai-org/GLM-4.6V-Flash"}})
    assert isinstance(client, Glm46VFlashClient)
