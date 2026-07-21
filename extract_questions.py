"""
Full-page OCR with a local vision model (VLM).
Reads page images / PDF and writes plain text + LaTeX to output/:
  output/<source>.txt
  output/<source>.tex
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import torch
import yaml

CONFIG_PATH = Path("config/extraction_config.yaml")

OCR_PROMPT_ZH = """請完整讀取這張頁面圖片中的所有文字與版面內容。

要求：
1. 盡量依閱讀順序（由上到下、由左到右）完整轉錄整頁可見內容，不要只取每段第一句。
2. 包含標題、說明、題號、題幹、小題 (a)(b)(c)、選項、答案、註解、頁首頁尾等所有文字。
3. 有圖／表時，把圖中可見的數字、標籤、條件也寫成文字。
4. 數學公式用 LaTeX：行內 $...$，區塊 $$...$$；不要省略。
5. 不要翻譯、不要摘要、不要解釋、不要評論。
6. 不要輸出 JSON、markdown 標題、代碼圍欄、\\documentclass 或任何包裝格式。
7. 只輸出頁面內容本身。
"""

OCR_PROMPT_EN = """Transcribe ALL visible text and layout content on this page image.

Rules:
1. Follow reading order (top-to-bottom, left-to-right). Capture the FULL page, not just the first sentence of each block.
2. Include titles, instructions, question numbers, stems, subparts (a)(b)(c), choices, answers, notes, headers/footers — everything visible.
3. For figures/tables, write down visible numbers, labels, and conditions as text.
4. Math must use LaTeX: inline $...$, display $$...$$. Do not omit formulas.
5. Do not translate, summarize, explain, or comment.
6. Do not output JSON, markdown headings, code fences, \\documentclass, or any wrapper format.
7. Output ONLY the page content itself.
"""


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ocr_prompt_for_lang(lang: str) -> str:
    lang = lang.lower().strip()
    if lang in {"en", "english"}:
        return OCR_PROMPT_EN
    if lang in {"zh", "zh-hant", "zh_tw", "chinese"}:
        return OCR_PROMPT_ZH
    raise ValueError(f"Unsupported lang: {lang}. Use en or zh.")


def normalize_lang(lang: str) -> str:
    lang = lang.lower().strip()
    if lang in {"en", "english"}:
        return "en"
    if lang in {"zh", "zh-hant", "zh_tw", "chinese"}:
        return "zh"
    raise ValueError(f"Unsupported lang: {lang}. Use en or zh.")


def check_gpu() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA GPU not detected. Local VLM needs NVIDIA + CUDA PyTorch.\n"
            "Install: pip install torch --index-url https://download.pytorch.org/whl/cu126"
        )
    name = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f"GPU: {name} | VRAM: {vram:.1f} GB")
    if vram < 10:
        print("Warning: VRAM below 10GB; use lower max_pixels if OOM.")


def list_images(images_dir: Path) -> list[Path]:
    if not images_dir.exists():
        raise FileNotFoundError(f"Images dir not found: {images_dir}")
    files = sorted(
        p for p in images_dir.iterdir()
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    if not files:
        raise FileNotFoundError(f"No images in {images_dir}")
    return files


def page_number_from_name(path: Path) -> int:
    m = re.search(r"(\d+)", path.stem)
    return int(m.group(1)) if m else 0


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:\w+)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def clean_ocr_text(text: str) -> str:
    """Remove accidental wrappers; keep content only."""
    text = strip_code_fence(text)
    # Drop leading assistant chat markers if any
    text = re.sub(r"^(assistant|Assistant)\s*[:：]\s*", "", text).strip()
    return text


def load_vlm(backend_cfg: dict):
    try:
        from transformers import AutoProcessor, BitsAndBytesConfig
    except ImportError as e:
        raise SystemExit(
            "Missing vision deps. Install with:\n"
            "  .\\.venv\\Scripts\\pip.exe install -r requirements-extract.txt"
        ) from e

    model_name = backend_cfg["model_name"]
    load_in_4bit = bool(backend_cfg.get("load_in_4bit", True))

    bnb_config = None
    if load_in_4bit:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    print(f"Loading VLM: {model_name} (4bit={load_in_4bit})")
    processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
    model_kwargs: dict = {
        "device_map": "auto",
        "trust_remote_code": True,
    }
    if bnb_config is not None:
        model_kwargs["quantization_config"] = bnb_config
    else:
        model_kwargs["torch_dtype"] = torch.bfloat16

    model = None
    if "glm-4.6v" in model_name.lower():
        try:
            from transformers import Glm4vForConditionalGeneration

            model = Glm4vForConditionalGeneration.from_pretrained(model_name, **model_kwargs)
            print("Using Glm4vForConditionalGeneration loader.")
        except ImportError:
            model = None

    if model is None:
        from transformers import AutoModelForImageTextToText

        try:
            model = AutoModelForImageTextToText.from_pretrained(model_name, **model_kwargs)
            print("Using AutoModelForImageTextToText loader.")
        except Exception as e:
            raise SystemExit(
                "Failed to load VLM model. If using GLM-4.6V-Flash, upgrade transformers first:\n"
                "  .\\.venv\\Scripts\\pip.exe install -U transformers\n"
                f"Original error: {e}"
            ) from e

    model.eval()
    return model, processor


def _as_int(value, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if re.fullmatch(r"\d+", text):
        return int(text)
    if re.fullmatch(r"[\d\s\*]+", text):
        result = 1
        for part in text.split("*"):
            part = part.strip()
            if part:
                result *= int(part)
        return result
    return int(text)


def _resize_for_pixel_budget(image, *, max_pixels: int, min_pixels: int):
    width, height = image.size
    pixels = width * height
    if max_pixels > 0 and pixels > max_pixels:
        scale = (max_pixels / float(pixels)) ** 0.5
        width = max(1, int(width * scale))
        height = max(1, int(height * scale))
        image = image.resize((width, height))
        pixels = width * height
    if min_pixels > 0 and pixels < min_pixels:
        scale = (min_pixels / float(pixels)) ** 0.5
        width = max(1, int(width * scale))
        height = max(1, int(height * scale))
        image = image.resize((width, height))
    return image


def run_vlm_on_image(
    model,
    processor,
    image_path: Path,
    prompt: str,
    backend_cfg: dict,
) -> str:
    try:
        from PIL import Image
    except ImportError as e:
        raise SystemExit(
            "Missing vision deps. Install with:\n"
            "  .\\.venv\\Scripts\\pip.exe install -r requirements-extract.txt"
        ) from e

    with Image.open(image_path) as im:
        image = im.convert("RGB")
        image.load()

    image = _resize_for_pixel_budget(
        image,
        max_pixels=_as_int(backend_cfg.get("max_pixels"), 0),
        min_pixels=_as_int(backend_cfg.get("min_pixels"), 0),
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    try:
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )
    except Exception:
        legacy_messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        text = processor.apply_chat_template(
            legacy_messages, tokenize=False, add_generation_prompt=True
        )
        inputs = processor(
            text=[text],
            images=[image],
            padding=True,
            return_tensors="pt",
        )

    inputs = inputs.to(model.device)
    inputs.pop("token_type_ids", None)

    temperature = float(backend_cfg.get("temperature", 0.1))
    gen_kwargs: dict = {
        "max_new_tokens": int(backend_cfg.get("max_new_tokens", 4096)),
        "do_sample": temperature > 0,
    }
    if temperature > 0:
        gen_kwargs["temperature"] = temperature

    with torch.inference_mode():
        generated = model.generate(**inputs, **gen_kwargs)

    trimmed = generated[:, inputs["input_ids"].shape[1] :]
    out = processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    return out[0] if out else ""


def ensure_images_from_pdf(pdf_path: Path, cfg: dict) -> Path:
    from pdf_to_images import pdf_to_images, safe_stem

    pages_root = Path(cfg["paths"]["pages_dir"])
    out_dir = pages_root / safe_stem(pdf_path)
    if out_dir.exists() and any(out_dir.glob("page_*.png")):
        print(f"Reusing existing page images: {out_dir}")
        return out_dir
    dpi = int(cfg.get("pdf", {}).get("dpi", 200))
    print(f"Converting PDF -> images @ {dpi} DPI")
    pdf_to_images(pdf_path, out_dir, dpi=dpi)
    return out_dir


def default_out_paths(cfg: dict, source_id: str) -> tuple[Path, Path]:
    out_dir = Path(cfg["paths"].get("output_dir", "output"))
    txt_tpl = cfg["paths"].get("ocr_file", "output/{source}.txt")
    tex_tpl = cfg["paths"].get("tex_file", "output/{source}.tex")
    if "{source}" in txt_tpl:
        txt_path = Path(txt_tpl.format(source=source_id))
    else:
        txt_path = out_dir / f"{source_id}.txt"
    if "{source}" in tex_tpl:
        tex_path = Path(tex_tpl.format(source=source_id))
    else:
        tex_path = out_dir / f"{source_id}.tex"
    return txt_path, tex_path


_LATEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex_outside_math(text: str) -> str:
    """Escape LaTeX specials, but keep existing $...$ / $$...$$ math intact."""
    parts = re.split(r"(\$\$.*?\$\$|\$[^$]*\$)", text, flags=re.DOTALL)
    out: list[str] = []
    for part in parts:
        if part.startswith("$"):
            out.append(part)
        else:
            out.append("".join(_LATEX_SPECIAL.get(ch, ch) for ch in part))
    return "".join(out)


def to_latex_document(body: str, *, lang: str, source_id: str) -> str:
    body = escape_latex_outside_math(body.strip())
    # Preserve blank-line paragraph breaks
    body = re.sub(r"\n{3,}", "\n\n", body)
    if lang == "zh":
        preamble = (
            "\\documentclass[12pt]{ctexart}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage{geometry}\n"
            "\\geometry{margin=2.2cm}\n"
        )
    else:
        preamble = (
            "\\documentclass[12pt]{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage{geometry}\n"
            "\\geometry{margin=2.2cm}\n"
        )
    return (
        f"% Auto OCR export: {source_id}\n"
        f"{preamble}"
        "\\begin{document}\n\n"
        f"{body}\n\n"
        "\\end{document}\n"
    )


def write_text_file(path: Path, text: str, *, append: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append and path.exists() else "w"
    with path.open(mode, encoding="utf-8") as f:
        if mode == "a" and path.stat().st_size > 0 and text:
            f.write("\n\n")
        f.write(text)


def main() -> None:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="VLM full-page OCR -> .txt + .tex")
    parser.add_argument("--images", type=Path, default=None, help="Directory of page_*.png")
    parser.add_argument("--pdf", type=Path, default=None, help="PDF path (auto convert pages)")
    parser.add_argument(
        "--backend",
        choices=list(cfg["backends"].keys()),
        default=cfg.get("active_backend", "local"),
    )
    parser.add_argument(
        "--lang",
        choices=["en", "zh"],
        default=normalize_lang(cfg.get("extraction", {}).get("source_lang", "zh")),
        help="Source language (default zh)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output .txt path (default output/<source>.txt); .tex is written beside it",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output files instead of appending",
    )
    parser.add_argument("--limit", type=int, default=0, help="Only process first N pages (0=all)")
    args = parser.parse_args()

    if not args.images and not args.pdf:
        parser.error("Provide --images DIR or --pdf FILE")

    images_dir = args.images
    source_pdf = ""
    if args.pdf:
        source_pdf = str(args.pdf).replace("\\", "/")
        images_dir = ensure_images_from_pdf(args.pdf, cfg)
    else:
        source_pdf = images_dir.name if images_dir else ""

    assert images_dir is not None
    images = list_images(images_dir)
    if args.limit > 0:
        images = images[: args.limit]

    backend_cfg = dict(cfg["backends"][args.backend])
    lang = normalize_lang(args.lang)
    prompt = ocr_prompt_for_lang(lang)
    print(f"Source lang: {lang} | mode: full_page OCR (.txt + .tex)")

    check_gpu()
    model, processor = load_vlm(backend_cfg)

    source_id = Path(source_pdf).stem if source_pdf else images_dir.name
    source_id = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", source_id) or "source"
    txt_path, tex_path = default_out_paths(cfg, source_id)
    if args.out is not None:
        txt_path = args.out
        tex_path = args.out.with_suffix(".tex")
    txt_path.parent.mkdir(parents=True, exist_ok=True)

    append = bool(cfg.get("extraction", {}).get("append", True)) and not args.overwrite
    page_texts: list[str] = []

    for image_path in images:
        page = page_number_from_name(image_path)
        print(f"\n=== OCR page {page}: {image_path} ===")
        try:
            raw = run_vlm_on_image(model, processor, image_path, prompt, backend_cfg)
            text = clean_ocr_text(raw)
        except Exception as e:
            print(f"FAILED page {page}: {e}", file=sys.stderr)
            continue

        if not text:
            print(f"  empty OCR for page {page}")
            continue

        page_texts.append(text)
        print(f"  ok ({len(text)} chars)")

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    if not page_texts:
        print("No OCR text extracted.")
        raise SystemExit(1)

    combined = "\n\n".join(page_texts)
    write_text_file(txt_path, combined, append=append)

    # .tex is always rebuilt from the final .txt content when overwriting;
    # when appending, rebuild from current combined blob appended to existing txt body.
    if append and txt_path.exists():
        full_txt = txt_path.read_text(encoding="utf-8")
    else:
        full_txt = combined
    tex_doc = to_latex_document(full_txt, lang=lang, source_id=source_id)
    tex_path.write_text(tex_doc, encoding="utf-8")

    action = "Appended" if append else "Wrote"
    print(f"\n{action} {len(page_texts)} page(s)")
    print(f"  TXT: {txt_path}")
    print(f"  TEX: {tex_path}")


if __name__ == "__main__":
    main()
