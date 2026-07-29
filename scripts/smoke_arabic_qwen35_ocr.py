"""Smoke-load sherif1313/Arabic-Qwen3.5-OCR-v4 (isolated transformers 5.x env).

This is an *Arabic* OCR specialty model (Qwen3.5-0.8B), not a drop-in for
Traditional Chinese DSE MCQ trunk (Qwen3-VL-8B). Use for bakeoff only.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

MODEL_ID = "sherif1313/Arabic-Qwen3.5-OCR-v4"


def _check_transformers() -> None:
    import transformers

    ver = transformers.__version__
    major = int(ver.split(".", 1)[0])
    if major < 5:
        raise SystemExit(
            f"Need transformers>=5.3 for Qwen3_5 (got {ver}). "
            "Use .venv-arabic-ocr, not main .venv."
        )
    try:
        from transformers import Qwen3_5ForConditionalGeneration  # noqa: F401
    except ImportError as e:
        raise SystemExit(f"Qwen3_5ForConditionalGeneration missing: {e}") from e


def load_model(model_id: str = MODEL_ID):
    import torch
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"[smoke] device={device} dtype={dtype} model={model_id}", flush=True)
    t0 = time.perf_counter()
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        model_id,
        dtype=dtype,
        device_map="auto" if device == "cuda" else None,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    model.eval()
    print(f"[smoke] loaded in {time.perf_counter() - t0:.1f}s", flush=True)
    return model, processor, device


def extract_text(
    model,
    processor,
    image_path: Path,
    *,
    prompt: str,
    device: str,
    max_new_tokens: int = 512,
) -> str:
    import torch
    from PIL import Image

    try:
        from qwen_vl_utils import process_vision_info
    except ImportError:
        process_vision_info = None

    image = Image.open(image_path).convert("RGB")
    w, h = image.size
    new_w = ((w + 63) // 64) * 64
    new_h = ((h + 63) // 64) * 64
    if (new_w, new_h) != (w, h):
        image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    text_input = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    if process_vision_info is not None:
        image_inputs, _ = process_vision_info(messages)
        inputs = processor(
            text=[text_input],
            images=image_inputs,
            padding=True,
            return_tensors="pt",
        )
    else:
        inputs = processor(
            text=[text_input],
            images=[image],
            padding=True,
            return_tensors="pt",
        )
    inputs = inputs.to(device)
    inputs.pop("token_type_ids", None)

    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            repetition_penalty=1.2,
            no_repeat_ngram_size=3,
            pad_token_id=getattr(processor.tokenizer, "pad_token_id", None),
            eos_token_id=getattr(processor.tokenizer, "eos_token_id", None),
        )
    trimmed = generated[:, inputs["input_ids"].shape[1] :]
    out = processor.batch_decode(
        trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    return (out[0] if out else "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument(
        "--image",
        type=Path,
        default=Path("output/crops/p002_q001.png"),
        help="Crop/page image (default: 2015p2 Q1 crop if present)",
    )
    parser.add_argument(
        "--prompt",
        default="Read all the text in the image.",
        help="OCR prompt (model card default is Arabic)",
    )
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args()

    _check_transformers()
    if not args.image.exists():
        print(f"[smoke] image missing: {args.image}", file=sys.stderr)
        print("[smoke] load-only OK path — pass --image when ready", flush=True)
        load_model(args.model)
        return 0

    model, processor, device = load_model(args.model)
    t0 = time.perf_counter()
    text = extract_text(
        model,
        processor,
        args.image,
        prompt=args.prompt,
        device=device,
        max_new_tokens=args.max_new_tokens,
    )
    dt = time.perf_counter() - t0
    print(f"[smoke] infer {dt:.2f}s chars={len(text)}", flush=True)
    out_path = Path("output") / "smoke_arabic_qwen35_ocr.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"[smoke] wrote {out_path}", flush=True)
    try:
        print("---", flush=True)
        print(text, flush=True)
        print("---", flush=True)
    except UnicodeEncodeError:
        print("[smoke] (console encoding cannot print text; see output file)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
