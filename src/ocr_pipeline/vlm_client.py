"""Qwen VLM client used by the OCR pipeline."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import torch


@runtime_checkable
class VlmClient(Protocol):
    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str: ...


def resize_image(image: Any, max_pixels: int) -> Any:
    """Downscale PIL image when pixel count exceeds ``max_pixels``."""
    w, h = image.size
    pixels = w * h
    if max_pixels > 0 and pixels > max_pixels:
        scale = (max_pixels / float(pixels)) ** 0.5
        image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    return image


def strip_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        import re

        text = re.sub(r"^```(?:\w+)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def resolve_stop_token_ids(processor: Any, model: Any) -> dict[str, Any]:
    """eos/pad for generate(); without them greedy decode may burn full max_new_tokens.

    Prefer ``model.generation_config.eos_token_id`` when set — Qwen2.5-VL uses a
    *list* (``<|im_end|>`` + ``<|endoftext|>``). Passing only the tokenizer's
    single eos can miss the alternate stop id and burn the full token budget.
    """
    tok = getattr(processor, "tokenizer", None) or processor
    eos = None
    pad = getattr(tok, "pad_token_id", None)

    gc = getattr(model, "generation_config", None)
    if gc is not None:
        gc_eos = getattr(gc, "eos_token_id", None)
        if gc_eos is not None:
            eos = gc_eos
        if pad is None:
            pad = getattr(gc, "pad_token_id", None)

    if eos is None:
        eos = getattr(tok, "eos_token_id", None)
    cfg = getattr(model, "config", None)
    if eos is None and cfg is not None:
        eos = getattr(cfg, "eos_token_id", None)
    if pad is None and cfg is not None:
        pad = getattr(cfg, "pad_token_id", None)
    if pad is None:
        pad = eos[0] if isinstance(eos, (list, tuple)) and eos else eos
    out: dict[str, Any] = {}
    if eos is not None:
        out["eos_token_id"] = eos
    if pad is not None:
        out["pad_token_id"] = pad
    return out


def force_greedy_generation_config(model: Any) -> None:
    """Drop sampling flags on model.generation_config (avoids temperature-ignored warn)."""
    gc = getattr(model, "generation_config", None)
    if gc is None:
        return
    gc.do_sample = False
    for key in ("temperature", "top_p", "top_k"):
        if hasattr(gc, key):
            with suppress(Exception):
                setattr(gc, key, None)


def build_generation_kwargs(
    *,
    max_new_tokens: int,
    temperature: float,
    eos_token_id: Any = None,
    pad_token_id: Any = None,
) -> dict:
    """
    Always use greedy decoding for OCR/VLM.

    temperature>0 previously enabled do_sample=True, which triggered a CUDA
    device-side assert inside torch.multinomial on Qwen2.5-VL 4bit.
    """
    _ = temperature  # retained for config/API compatibility
    kwargs: dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "do_sample": False,
    }
    if eos_token_id is not None:
        kwargs["eos_token_id"] = eos_token_id
    if pad_token_id is not None:
        kwargs["pad_token_id"] = pad_token_id
    return kwargs


def run_vlm_generate(
    *,
    model: Any,
    processor: Any,
    prompt: str,
    image_path: Path | None,
    max_pixels: int,
    max_new_tokens: int,
    temperature: float,
    strip_output_fences: bool = True,
) -> str:
    """Shared chat-template → greedy generate → decode path for Qwen clients."""
    content: list[dict] = []
    pil_image = None
    if image_path is not None:
        from PIL import Image

        with Image.open(image_path) as im:
            pil_image = im.convert("RGB")
            pil_image.load()
        pil_image = resize_image(pil_image, max_pixels)
        content.append({"type": "image", "image": pil_image})
    content.append({"type": "text", "text": prompt})
    messages = [{"role": "user", "content": content}]

    try:
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )
    except Exception:
        if pil_image is None:
            text = processor.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = processor(text=[text], return_tensors="pt")
        else:
            legacy = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            text = processor.apply_chat_template(legacy, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[text], images=[pil_image], padding=True, return_tensors="pt")

    inputs = inputs.to(model.device)
    inputs.pop("token_type_ids", None)

    stop_ids = resolve_stop_token_ids(processor, model)
    gen_kwargs = build_generation_kwargs(
        max_new_tokens=int(max_new_tokens),
        temperature=temperature,
        eos_token_id=stop_ids.get("eos_token_id"),
        pad_token_id=stop_ids.get("pad_token_id"),
    )

    with torch.inference_mode():
        generated = model.generate(**inputs, **gen_kwargs)
    trimmed = generated[:, inputs["input_ids"].shape[1] :]
    n_new = int(trimmed.shape[1]) if trimmed.ndim == 2 else 0
    # Flat ~40–50s/block usually means we burned max_new_tokens (no early EOS).
    if max_new_tokens > 0 and n_new >= int(max_new_tokens * 0.9):
        print(
            f"[VLM] WARN near-max tokens: n_new={n_new} max={max_new_tokens}",
            flush=True,
        )
    out = processor.batch_decode(
        trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    text = out[0] if out else ""
    if strip_output_fences:
        text = strip_fences(text)
    del inputs, generated, trimmed
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return text


class QwenVlClient:
    """Qwen2.5-VL / Qwen3-VL Instruct (default 4bit) for RTX 4070 Super 12GB."""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-VL-8B-Instruct",
        *,
        load_in_4bit: bool = True,
        max_new_tokens: int = 2048,
        temperature: float = 0.0,
        max_pixels: int = 1003520,
    ):
        self.model_name = model_name
        self.load_in_4bit = load_in_4bit
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.max_pixels = max_pixels
        self.model = None
        self.processor = None

    @staticmethod
    def _load_causal_vlm(model_name: str, model_kwargs: dict) -> Any:
        """Prefer the matching Qwen VL class; fall back for older checkpoints."""
        name = model_name.lower()
        if "qwen3-vl" in name or "qwen3_vl" in name:
            try:
                from transformers import Qwen3VLForConditionalGeneration

                return Qwen3VLForConditionalGeneration.from_pretrained(
                    model_name, **model_kwargs
                )
            except Exception:
                pass
        if "qwen2.5-vl" in name or "qwen2_5_vl" in name:
            try:
                from transformers import Qwen2_5_VLForConditionalGeneration

                return Qwen2_5_VLForConditionalGeneration.from_pretrained(
                    model_name, **model_kwargs
                )
            except Exception:
                pass
        try:
            from transformers import Qwen3VLForConditionalGeneration

            return Qwen3VLForConditionalGeneration.from_pretrained(
                model_name, **model_kwargs
            )
        except Exception:
            pass
        try:
            from transformers import Qwen2_5_VLForConditionalGeneration

            return Qwen2_5_VLForConditionalGeneration.from_pretrained(
                model_name, **model_kwargs
            )
        except Exception:
            from transformers import AutoModelForImageTextToText

            return AutoModelForImageTextToText.from_pretrained(
                model_name, **model_kwargs
            )

    def load(self) -> None:
        if self.model is not None:
            return
        from transformers import AutoProcessor, BitsAndBytesConfig

        print(f"[Qwen] Loading {self.model_name} (4bit={self.load_in_4bit})")
        self.processor = AutoProcessor.from_pretrained(self.model_name, trust_remote_code=True)

        model_kwargs: dict = {
            "device_map": "auto",
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,
        }
        if self.load_in_4bit:
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
        else:
            model_kwargs["torch_dtype"] = torch.bfloat16

        self.model = self._load_causal_vlm(self.model_name, model_kwargs)
        self.model.eval()
        force_greedy_generation_config(self.model)

    def _generate(
        self,
        prompt: str,
        image_path: Path | None,
        *,
        max_new_tokens: int | None,
        strip_output_fences: bool,
    ) -> str:
        self.load()
        assert self.model is not None and self.processor is not None
        token_budget = self.max_new_tokens if max_new_tokens is None else int(max_new_tokens)
        return run_vlm_generate(
            model=self.model,
            processor=self.processor,
            prompt=prompt,
            image_path=image_path,
            max_pixels=self.max_pixels,
            max_new_tokens=token_budget,
            temperature=self.temperature,
            strip_output_fences=strip_output_fences,
        )

    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        return self._generate(
            prompt,
            image_path,
            max_new_tokens=max_new_tokens,
            strip_output_fences=True,
        )

    def generate_raw(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        return self._generate(
            prompt,
            image_path,
            max_new_tokens=max_new_tokens,
            strip_output_fences=False,
        )

    def close(self) -> None:
        self.model = None
        self.processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def build_vlm_client(cfg: dict | None = None) -> VlmClient:
    """Build the Qwen VLM from config."""
    cfg = cfg or {}
    vlm_cfg = dict(cfg.get("vlm") or {})
    backend = str(vlm_cfg.get("backend", "qwen")).lower()
    if backend != "qwen":
        raise ValueError(f"Unknown VLM backend: {backend}")

    return QwenVlClient(
        model_name=str(vlm_cfg.get("model_name", "Qwen/Qwen3-VL-8B-Instruct")),
        load_in_4bit=bool(vlm_cfg.get("load_in_4bit", True)),
        max_new_tokens=int(vlm_cfg.get("max_new_tokens", 2048)),
        temperature=float(vlm_cfg.get("temperature", 0.0)),
        max_pixels=int(vlm_cfg.get("max_pixels", 1003520)),
    )


def build_mcq_structured_client(
    cfg: dict | None = None,
    *,
    default_model_name: str = "Qwen/Qwen3-VL-8B-Instruct",
):
    """Build the optional OpenAI-compatible Instructor backend.

    This does not patch or replace the local Transformers Qwen client.
    """
    src = dict(cfg or {})
    if not bool(src.get("enabled", False)):
        return None
    backend = str(src.get("backend", "instructor_openai")).strip().lower()
    if backend != "instructor_openai":
        raise ValueError(f"Unknown structured OCR backend: {backend}")

    from .mcq_structured import InstructorMcqOcrClient

    model_name = str(src.get("model_name") or default_model_name)
    provider = str(src.get("provider") or f"openai/{model_name}")
    return InstructorMcqOcrClient(
        provider=provider,
        model_name=model_name,
        base_url=str(src.get("base_url") or "") or None,
        api_key_env=str(src.get("api_key_env") or "") or None,
        max_validation_retries=int(src.get("max_validation_retries", 1)),
    )
