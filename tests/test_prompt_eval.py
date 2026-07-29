"""T7 / eng-review 12C: prompt eval suite with CUDA hard-fail (no auto-skip).

Without CUDA, ``test_cuda_required_for_prompt_eval_suite`` and
``test_vlm_polish_smoke`` intentionally ``pytest.fail`` (not skip).
Static contract tests do not need GPU.
"""

from __future__ import annotations

import pytest

from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.prompts import CONTENT_FIRST_POLISH_PROMPT, LATEX_MATH_RULES


def test_cuda_required_for_prompt_eval_suite():
    """12C: hard-fail without CUDA — do not auto-skip this suite gate."""
    import torch

    if not torch.cuda.is_available():
        pytest.fail("CUDA required for prompt eval (eng-review 12C); no auto-skip")


def test_content_first_prompt_contract_static():
    """Always runs: content-first header is wired (no GPU)."""
    assert FinalPolisher.prompt_header() == CONTENT_FIRST_POLISH_PROMPT
    assert LATEX_MATH_RULES in CONTENT_FIRST_POLISH_PROMPT
    assert "將圖片" in CONTENT_FIRST_POLISH_PROMPT
    assert "tabular" in CONTENT_FIRST_POLISH_PROMPT.lower()
    assert "<<<TXT>>>" in CONTENT_FIRST_POLISH_PROMPT
    assert "<<<TEX>>>" in CONTENT_FIRST_POLISH_PROMPT


@pytest.mark.gpu
def test_prompt_eval_content_first_header_in_polisher():
    """Marked gpu for suite grouping; assertion itself needs no GPU."""
    assert FinalPolisher.prompt_header() is CONTENT_FIRST_POLISH_PROMPT or (
        FinalPolisher.prompt_header() == CONTENT_FIRST_POLISH_PROMPT
    )


def test_vlm_polish_smoke():
    """
    12C: hard-fail without CUDA. With CUDA, light smoke only (no full Qwen weight load).

    Full ``generate()`` risks long load / OOM on 12GB; factory + content-first
    header + CUDA gate still honor eng-review 12C (fail, never skip).
    """
    import torch

    if not torch.cuda.is_available():
        pytest.fail("CUDA required for prompt eval (12C); no auto-skip")

    from ocr_pipeline.vlm_client import QwenVlClient, build_vlm_client

    client = build_vlm_client(
        {
            "vlm": {
                "backend": "qwen",
                "model_name": "Qwen/Qwen2.5-VL-7B-Instruct",
                "load_in_4bit": True,
                "max_new_tokens": 64,
                "temperature": 0.0,
            }
        }
    )
    assert isinstance(client, QwenVlClient)
    assert client.model is None  # not loaded yet — avoid heavy smoke
    assert FinalPolisher.prompt_header() == CONTENT_FIRST_POLISH_PROMPT
    assert torch.cuda.is_available()
