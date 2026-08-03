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
    args = parser.parse_args()
    pipeline: Any | None = None

    for line in sys.stdin:
        try:
            request = json.loads(line)
            image_path = Path(str(request["image_path"]))
            if pipeline is None:
                from paddleocr import PaddleOCRVL

                with contextlib.redirect_stdout(sys.stderr):
                    pipeline = PaddleOCRVL(pipeline_version="v1.6", device=args.device)
            with contextlib.redirect_stdout(sys.stderr):
                text = _extract_markdown(pipeline.predict(str(image_path)))
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
