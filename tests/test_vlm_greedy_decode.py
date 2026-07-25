"""Regression: sampling path triggers CUDA multinomial assert on 4bit Qwen-VL."""

from __future__ import annotations

from types import SimpleNamespace

from ocr_pipeline.vlm_client import (
    build_generation_kwargs,
    build_vlm_client,
    force_greedy_generation_config,
    resolve_stop_token_ids,
)


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


def test_generation_kwargs_include_eos_and_pad_when_provided():
    kwargs = build_generation_kwargs(
        max_new_tokens=16,
        temperature=0.0,
        eos_token_id=151645,
        pad_token_id=151643,
    )
    assert kwargs["eos_token_id"] == 151645
    assert kwargs["pad_token_id"] == 151643
    assert kwargs["do_sample"] is False


def test_resolve_stop_token_ids_from_processor_tokenizer():
    processor = SimpleNamespace(tokenizer=SimpleNamespace(eos_token_id=7, pad_token_id=None))
    model = SimpleNamespace(
        generation_config=None,
        config=SimpleNamespace(eos_token_id=99, pad_token_id=None),
    )
    ids = resolve_stop_token_ids(processor, model)
    assert ids["eos_token_id"] == 7
    assert ids["pad_token_id"] == 7  # falls back to eos


def test_resolve_stop_token_ids_prefers_generation_config_list():
    """Qwen2.5-VL: generation_config.eos is [im_end, endoftext] — keep the list."""
    processor = SimpleNamespace(tokenizer=SimpleNamespace(eos_token_id=151645, pad_token_id=151643))
    model = SimpleNamespace(
        generation_config=SimpleNamespace(eos_token_id=[151645, 151643], pad_token_id=151643),
        config=SimpleNamespace(eos_token_id=151645, pad_token_id=151643),
    )
    ids = resolve_stop_token_ids(processor, model)
    assert ids["eos_token_id"] == [151645, 151643]
    assert ids["pad_token_id"] == 151643


def test_force_greedy_generation_config_clears_sampling_flags():
    gc = SimpleNamespace(do_sample=True, temperature=0.7, top_p=0.9, top_k=50)
    model = SimpleNamespace(generation_config=gc)
    force_greedy_generation_config(model)
    assert gc.do_sample is False
    assert gc.temperature is None
    assert gc.top_p is None
    assert gc.top_k is None


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
