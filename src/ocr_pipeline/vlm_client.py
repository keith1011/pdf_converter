"""VLM client seam: swappable Qwen / GLM adapters (same generate() API)."""

from __future__ import annotations

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


# Back-compat alias used by older call sites / tests
_resize = resize_image


def strip_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        import re

        text = re.sub(r"^```(?:\w+)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


_strip_fences = strip_fences


def build_generation_kwargs(*, max_new_tokens: int, temperature: float) -> dict:
    """
    Always use greedy decoding for OCR/VLM.

    temperature>0 previously enabled do_sample=True, which triggered a CUDA
    device-side assert inside torch.multinomial on Qwen2.5-VL 4bit.
    """
    _ = temperature  # retained for config/API compatibility
    return {
        "max_new_tokens": max_new_tokens,
        "do_sample": False,
    }


def run_vlm_generate(
    *,
    model: Any,
    processor: Any,
    prompt: str,
    image_path: Path | None,
    max_pixels: int,
    max_new_tokens: int,
    temperature: float,
) -> str:
    """Shared chat-template → greedy generate → decode path for Qwen/GLM."""
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

    gen_kwargs = build_generation_kwargs(
        max_new_tokens=int(max_new_tokens),
        temperature=temperature,
    )

    with torch.inference_mode():
        generated = model.generate(**inputs, **gen_kwargs)
    trimmed = generated[:, inputs["input_ids"].shape[1] :]
    out = processor.batch_decode(
        trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    text = strip_fences(out[0] if out else "")
    del inputs, generated, trimmed
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return text


class Qwen25VlClient:
    """Qwen2.5-VL-Instruct (default 4bit) for RTX 4070 Super 12GB."""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-VL-7B-Instruct",
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

        try:
            from transformers import Qwen2_5_VLForConditionalGeneration

            self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                self.model_name, **model_kwargs
            )
        except Exception:
            from transformers import AutoModelForImageTextToText

            self.model = AutoModelForImageTextToText.from_pretrained(
                self.model_name, **model_kwargs
            )
        self.model.eval()

    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
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
        )


def build_vlm_client(cfg: dict | None = None) -> VlmClient:
    """
    Build VLM from config.

    Prefer `vlm:` block (backend: qwen|glm). If missing, fall back to legacy `glm:`.
    """
    cfg = cfg or {}
    vlm_cfg = dict(cfg.get("vlm") or {})
    glm_cfg = dict(cfg.get("glm") or {})
    backend = str(vlm_cfg.get("backend") or ("qwen" if vlm_cfg else "glm")).lower()

    if backend == "glm":
        from .glm_client import Glm46VFlashClient

        src = {**glm_cfg, **{k: v for k, v in vlm_cfg.items() if k != "backend"}}
        return Glm46VFlashClient(
            model_name=str(src.get("model_name", "zai-org/GLM-4.6V-Flash")),
            load_in_4bit=bool(src.get("load_in_4bit", True)),
            max_new_tokens=int(src.get("max_new_tokens", 2048)),
            temperature=float(src.get("temperature", 0.0)),
            max_pixels=int(src.get("max_pixels", 1003520)),
        )

    # default: qwen
    src = {**vlm_cfg}
    return Qwen25VlClient(
        model_name=str(src.get("model_name", "Qwen/Qwen2.5-VL-7B-Instruct")),
        load_in_4bit=bool(src.get("load_in_4bit", True)),
        max_new_tokens=int(src.get("max_new_tokens", 2048)),
        temperature=float(src.get("temperature", 0.0)),
        max_pixels=int(src.get("max_pixels", 1003520)),
    )
