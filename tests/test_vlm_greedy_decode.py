"""Regression: sampling path triggers CUDA multinomial assert on 4bit Qwen-VL."""

from __future__ import annotations

from ocr_pipeline.vlm_client import build_generation_kwargs, build_vlm_client


def test_generation_kwargs_are_greedy_at_temperature_zero():
    kwargs = build_generation_kwargs(max_new_tokens=64, temperature=0.0)
    assert kwargs["do_sample"] is False
    assert "temperature" not in kwargs
    assert kwargs["max_new_tokens"] == 64


def test_generation_kwargs_reject_sampling_even_if_temperature_positive():
    """OCR must stay greedy: sampling caused device-side assert in multinomial."""
    kwargs = build_generation_kwargs(max_new_tokens=32, temperature=0.1)
    assert kwargs["do_sample"] is False
    assert "temperature" not in kwargs


def test_factory_defaults_temperature_to_zero():
    client = build_vlm_client(
        {"vlm": {"backend": "qwen", "model_name": "Qwen/Qwen2.5-VL-7B-Instruct"}}
    )
    assert client.temperature == 0.0


def test_factory_defaults_max_new_tokens_to_2048():
    client = build_vlm_client(
        {"vlm": {"backend": "qwen", "model_name": "Qwen/Qwen2.5-VL-7B-Instruct"}}
    )
    assert client.max_new_tokens == 2048


def test_route_token_budget_lower_than_polish_in_factory():
    from ocr_pipeline.factory import build_default_pipeline

    mgr = build_default_pipeline(
        {
            "vlm": {
                "backend": "qwen",
                "model_name": "Qwen/Qwen2.5-VL-7B-Instruct",
                "max_new_tokens": 2048,
                "max_new_tokens_route": 1024,
            },
            "paths": {"output_dir": "output", "pages_dir": "data/pdf_pages", "crop_dir": "output/crops"},
        }
    )
    assert mgr.router.text_router.max_new_tokens == 1024
    assert mgr.router.math_router.max_new_tokens == 1024
    assert mgr.polisher.vlm.max_new_tokens == 2048
