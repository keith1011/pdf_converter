"""TDD: Layer A admit_segment rules (quality gate)."""

from __future__ import annotations

from ocr_pipeline.quality import admit_segment


def test_drops_empty():
    assert admit_segment({"kind": "prose", "text": "   "}) is False


def test_drops_bare_option_letter():
    assert admit_segment({"kind": "prose", "text": "A."}) is False
    assert admit_segment({"kind": "prose", "text": "B．"}) is False


def test_drops_punct_and_paren_only():
    assert admit_segment({"kind": "prose", "text": "("}) is False
    assert admit_segment({"kind": "prose", "text": "。"}) is False


def test_drops_single_cjk_and_lone_qnum():
    assert admit_segment({"kind": "prose", "text": "一"}) is False
    assert admit_segment({"kind": "prose", "text": "12."}) is False


def test_prose_requires_len_12():
    assert admit_segment({"kind": "prose", "text": "短文字不足"}) is False
    assert admit_segment({"kind": "prose", "text": "這段散文夠長可以進向量庫了"}) is True


def test_math_requires_len_8_and_latexish():
    assert admit_segment({"kind": "math", "text": "x=1"}) is False  # len 3
    assert admit_segment({"kind": "math", "text": "abcdefghi"}) is False  # len>=8 but not latexish
    assert admit_segment({"kind": "math", "text": r"\frac{1}{n}"}) is True
    assert admit_segment({"kind": "math", "text": "$a+b=c+d$"}) is True


def test_figure_needs_caption_and_crop():
    assert admit_segment({"kind": "figure", "text": "二次函數圖像", "crop_path": "figures/a.png"}) is True
    assert admit_segment({"kind": "figure", "text": "圖", "crop_path": "figures/a.png"}) is False
    assert admit_segment({"kind": "figure", "text": "圖示足夠", "crop_path": None}) is False


def test_mark_note_len_8():
    assert admit_segment({"kind": "mark_note", "text": "短"}) is False
    assert admit_segment({"kind": "mark_note", "text": "1M 給分註記OK"}) is True
