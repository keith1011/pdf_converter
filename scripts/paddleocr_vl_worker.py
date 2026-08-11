"""JSONL worker for PaddleOCR-VL's isolated CUDA/cuDNN runtime."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any


def _extract_markdown(results: Any) -> str:
    parts: list[str] = []
    for result in results:
        markdown = getattr(result, "markdown", None)
        if isinstance(markdown, dict) and isinstance(markdown.get("markdown_texts"), str):
            parts.append(markdown["markdown_texts"].strip())
    return "\n".join(part for part in parts if part)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="gpu")
    parser.add_argument("--disable-layout-detection", action="store_true")
    parser.add_argument("--max-pixels", type=int)
    parser.add_argument("--precision", choices=("fp32", "fp16"))
    args = parser.parse_args()
    pipeline: Any | None = None

    for line in sys.stdin:
        try:
            request = json.loads(line)
            image_path = Path(str(request["image_path"]))
            if pipeline is None:
                from paddleocr import PaddleOCRVL

                pipeline_kwargs: dict[str, Any] = {
                    "pipeline_version": "v1.6",
                    "device": args.device,
                }
                if args.disable_layout_detection:
                    pipeline_kwargs["use_layout_detection"] = False
                if args.precision is not None:
                    pipeline_kwargs["precision"] = args.precision
                with contextlib.redirect_stdout(sys.stderr):
                    pipeline = PaddleOCRVL(**pipeline_kwargs)
            predict_kwargs: dict[str, Any] = {}
            if args.max_pixels is not None:
                predict_kwargs["max_pixels"] = args.max_pixels
            with contextlib.redirect_stdout(sys.stderr):
                text = _extract_markdown(pipeline.predict(str(image_path), **predict_kwargs))
            response: dict[str, str] = {"text": text}
        except Exception as exc:
            response = {"error": f"{type(exc).__name__}: {exc}"}
        # The parent process uses JSON Lines over a Windows pipe.  Keep the
        # transport ASCII-only so console code-page differences cannot turn
        # CJK OCR text into mojibake before it reaches the main pipeline.
        print(json.dumps(response, ensure_ascii=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
