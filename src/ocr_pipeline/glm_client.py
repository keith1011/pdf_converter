"""Local GLM-4.6V-Flash client (shared by TextRouter + FinalPolisher)."""

from __future__ import annotations

from pathlib import Path

import torch


class Glm46VFlashClient:
    """Thin wrapper around local zai-org/GLM-4.6V-Flash."""

    def __init__(
        self,
        model_name: str = "zai-org/GLM-4.6V-Flash",
        *,
        load_in_4bit: bool = True,
        max_new_tokens: int = 4096,
        temperature: float = 0.1,
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

        print(f"[GLM] Loading {self.model_name} (4bit={self.load_in_4bit})")
        self.processor = AutoProcessor.from_pretrained(self.model_name, trust_remote_code=True)

        model_kwargs: dict = {"device_map": "auto", "trust_remote_code": True}
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
            from transformers import Glm4vForConditionalGeneration

            self.model = Glm4vForConditionalGeneration.from_pretrained(
                self.model_name, **model_kwargs
            )
        except Exception:
            from transformers import AutoModelForImageTextToText

            self.model = AutoModelForImageTextToText.from_pretrained(
                self.model_name, **model_kwargs
            )
        self.model.eval()

    @staticmethod
    def _resize(image, max_pixels: int):
        w, h = image.size
        pixels = w * h
        if max_pixels > 0 and pixels > max_pixels:
            scale = (max_pixels / float(pixels)) ** 0.5
            image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        return image

    def generate(self, prompt: str, image_path: Path | None = None) -> str:
        self.load()
        assert self.model is not None and self.processor is not None

        content: list[dict] = []
        pil_image = None
        if image_path is not None:
            from PIL import Image

            with Image.open(image_path) as im:
                pil_image = im.convert("RGB")
                pil_image.load()
            pil_image = self._resize(pil_image, self.max_pixels)
            content.append({"type": "image", "image": pil_image})
        content.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content}]

        try:
            inputs = self.processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
            )
        except Exception:
            # Text-only or legacy path
            if pil_image is None:
                text = self.processor.apply_chat_template(
                    [{"role": "user", "content": prompt}],
                    tokenize=False,
                    add_generation_prompt=True,
                )
                inputs = self.processor(text=[text], return_tensors="pt")
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
                text = self.processor.apply_chat_template(
                    legacy, tokenize=False, add_generation_prompt=True
                )
                inputs = self.processor(
                    text=[text], images=[pil_image], padding=True, return_tensors="pt"
                )

        inputs = inputs.to(self.model.device)
        inputs.pop("token_type_ids", None)

        gen_kwargs: dict = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": self.temperature > 0,
        }
        if self.temperature > 0:
            gen_kwargs["temperature"] = self.temperature

        with torch.inference_mode():
            generated = self.model.generate(**inputs, **gen_kwargs)
        trimmed = generated[:, inputs["input_ids"].shape[1] :]
        out = self.processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        text = (out[0] if out else "").strip()
        if text.startswith("```"):
            import re

            text = re.sub(r"^```(?:\w+)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        text = text.strip()
        del inputs, generated, trimmed
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return text
