"""Per-question stitch / polish boundaries (MCQ layout → emit)."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.assemble import DraftAssembler, FinalPolisher, format_mcq_question_text
from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.pylatex_assist import encode_unicode_outside_math


def _block(qid: int, text: str, *, page: int = 2, order: int = 0) -> LayoutBlock:
    return LayoutBlock(
        block_id=f"p{page:03d}_q{qid:03d}",
        block_type=BlockType.TEXT,
        bbox=BBox(0, 0, 10, 10),
        order=order,
        page=page,
        image_path=Path("x.png"),
        raw_text=text,
        meta={"question_id": qid},
    )


def test_format_mcq_question_text_prefixes_missing_number():
    assert format_mcq_question_text("$(x+1)=$", 2).startswith("2.")
    assert format_mcq_question_text("2. already", 2).startswith("2.")


def test_stitch_mcq_blocks_separates_with_blank_line_and_numbers():
    blocks = [
        _block(1, "A. $x^3+1$\nB. $(x+1)^3$", order=0),
        _block(2, r"$\frac{(3y)^3}{3y^2}=$" "\nA. $4y^5$", order=1),
    ]
    draft = DraftAssembler().stitch(blocks)
    assert "\n\n" in draft
    parts = [p for p in draft.split("\n\n") if p.strip()]
    assert len(parts) == 2
    assert parts[0].startswith("1.")
    assert parts[1].startswith("2.")
    # Must not glue Q1 options onto Q2 stem
    assert "B. $(x+1)^3$ $\\frac" not in draft.replace("\n", " ")


def test_polish_runs_per_question_not_whole_page():
    """Default MCQ Stage3 is sanitize — no VLM; blank-line boundaries kept."""

    class BoomVlm:
        def generate(self, prompt, image_path=None, *, max_new_tokens=None):
            raise AssertionError("sanitize mode must not call VLM")

    draft = "1. stem one\nA. 1\n\n2. stem two\nA. 2"
    txt, tex, warn = FinalPolisher(BoomVlm(), mcq_stage3="sanitize").polish(draft)
    assert any("sanitize" in w for w in warn)
    body = FinalPolisher.extract_tex_body(tex)
    assert "1." in body and "2." in body
    assert "\n\n" in body


def test_polish_vlm_mode_still_splits_per_question():
    calls: list[str] = []

    class FakeVlm:
        def generate(self, prompt, image_path=None, *, max_new_tokens=None):
            draft = prompt.split("草稿：", 1)[-1].strip()
            calls.append(draft)
            return (
                f"<<<TXT>>>\n{draft}\n<<<TEX>>>\n"
                f"\\documentclass{{ctexart}}\\begin{{document}}\n"
                f"{draft}\n\\end{{document}}"
            )

    draft = "1. stem one\nA. 1\n\n2. stem two\nA. 2"
    txt, tex, warn = FinalPolisher(FakeVlm(), mcq_stage3="vlm").polish(draft)
    assert len(calls) == 2
    assert calls[0].startswith("1.")
    assert calls[1].startswith("2.")
    body = FinalPolisher.extract_tex_body(tex)
    assert "1." in body and "2." in body
    assert "\n\n" in body


def test_encode_unicode_outside_math_keeps_frac():
    src = r"若 α 滿足 $\frac{a}{b}=1$，則 β≤0"
    out = encode_unicode_outside_math(src)
    assert r"\frac{a}{b}" in out
    assert "α" not in out
    assert "若" in out  # CJK kept (not dropped, not warned away)
    assert "β" not in out or "beta" in out.lower() or "ensuremath" in out


def test_encode_unicode_keeps_cjk_quietly():
    """Regression: CJK must not be deleted or spam 'No known latex representation'."""
    import io
    import sys

    buf = io.StringIO()
    old = sys.stderr
    try:
        sys.stderr = buf
        out = encode_unicode_outside_math("設 k 為常數，α≤1")
    finally:
        sys.stderr = old
    assert "設" in out and "為" in out
    assert "No known latex representation" not in buf.getvalue()
