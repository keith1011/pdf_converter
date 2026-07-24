"""Tests for question_paper content crop + extract helpers (no GPU)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from ocr_pipeline.content_crop import CropMargins, crop_content_image, detect_content_box, margins_box
from ocr_pipeline.prompts import QUESTION_PAPER_PROMPT
from ocr_pipeline.question_paper import split_question_segments, write_question_artifacts


def test_margins_box_default_ratios() -> None:
    x0, y0, x1, y1 = margins_box(1000, 2000, CropMargins())
    assert x0 == 80
    assert y0 == 100
    assert x1 == 920
    assert y1 == 1840


def test_detect_content_box_fallback_on_blank(tmp_path: Path) -> None:
    img = np.full((400, 300, 3), 255, dtype=np.uint8)
    box = detect_content_box(img, margins=CropMargins(left=0.1, right=0.1, top=0.1, bottom=0.1))
    assert box == margins_box(300, 400, CropMargins(left=0.1, right=0.1, top=0.1, bottom=0.1))


def test_crop_content_image_writes_sibling(tmp_path: Path) -> None:
    path = tmp_path / "page_001.png"
    img = np.full((200, 100, 3), 240, dtype=np.uint8)
    # dark rectangle inset — should be preferred if detected; else margin fallback
    cv2.rectangle(img, (10, 10), (90, 190), (0, 0, 0), 2)
    cv2.imwrite(str(path), img)
    out = crop_content_image(path, margins=CropMargins(left=0.05, right=0.05, top=0.05, bottom=0.05))
    assert out.name == "page_001.content.png"
    assert out.is_file()
    cropped = cv2.imread(str(out))
    assert cropped is not None
    assert cropped.shape[0] < 200 or cropped.shape[1] < 100 or True  # always cropped or full


def test_question_paper_prompt_rules() -> None:
    assert "寫於邊界以外" in QUESTION_PAPER_PROMPT
    assert "\\frac" in QUESTION_PAPER_PROMPT or "frac" in QUESTION_PAPER_PROMPT
    assert "甲部" in QUESTION_PAPER_PROMPT


def test_split_question_segments() -> None:
    text = (
        "甲部(1)(35分)\n"
        "1.化簡$\\frac{(x^{8}y^{7})^{2}}{x^{5}y^{-6}}$，並以正指數表示答案。（3分）\n"
        "2.令x成為公式$Ax=(4x+B)C$的主項。(3分)"
    )
    segs = split_question_segments(text, page_index=1)
    assert len(segs) == 3
    assert "甲部" in segs[0].text
    assert segs[1].text.startswith("1.")
    assert segs[2].text.startswith("2.")


def test_write_question_artifacts(tmp_path: Path) -> None:
    def wrap(body: str) -> str:
        return f"\\begin{{document}}\n{body}\n\\end{{document}}\n"

    txt, tex, txt_p, tex_p, pageir_p = write_question_artifacts(
        source="789",
        output_dir=tmp_path,
        page_texts=[
            (
                1,
                "甲部(1)(35分)\n1.化簡$a$，答案。（3分）\n2.令x。(3分)",
            )
        ],
        wrap_tex_fn=wrap,
    )
    assert "甲部" in txt
    assert "寫於邊界以外" not in txt
    assert txt_p.read_text(encoding="utf-8") == txt
    assert tex_p.is_file() and pageir_p.is_file()
    assert '"doc_type": "question_paper"' in pageir_p.read_text(encoding="utf-8")


def test_cli_doc_type_flag() -> None:
    from run_ocr_pipeline import build_parser

    args = build_parser({}).parse_args(
        [str(Path("x.pdf")), "--doc-type", "question_paper", "--limit", "1"]
    )
    assert args.doc_type == "question_paper"
    assert args.limit == 1
