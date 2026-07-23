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
