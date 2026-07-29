"""Recover TeX when VLM wraps output in markdown / prose."""

from __future__ import annotations

from ocr_pipeline.assemble import FinalPolisher, _looks_like_math_rules_echo


def test_extract_tex_from_markdown_fence():
    raw = """以下是修正後的版本：

```latex
\\documentclass[12pt]{ctexart}
\\begin{document}
hi
\\end{document}
```

這段確保公式正確。
"""
    got = FinalPolisher._extract_tex_document(raw)
    assert got is not None
    assert got.startswith("\\documentclass")
    assert got.endswith("\\end{document}")
    assert "以下是" not in got
    assert "```" not in got


def test_parse_accepts_extracted_complete_document_without_partial_warning():
    class FakeVlm:
        def generate(self, prompt, image_path=None):
            return (
                "說明文字\n```latex\n"
                "\\documentclass{ctexart}\\begin{document}x\\end{document}\n"
                "```\n結尾"
            )

    txt, tex, warn = FinalPolisher(FakeVlm()).polish("draft")
    assert "\\documentclass" in tex
    assert tex.strip().startswith("\\documentclass")
    assert "說明" not in tex
    assert txt == "x"
    assert not any("parse partial" in item for item in warn)


def test_polish_skips_vlm_on_blank_draft():
    class BoomVlm:
        def generate(self, prompt, image_path=None):
            raise AssertionError("blank draft must not call VLM")

    txt, tex, warn = FinalPolisher(BoomVlm()).polish("   \n\t  ")
    assert txt == ""
    assert "\\begin{document}" in tex
    assert warn == []


def test_polish_rejects_math_rules_echo():
    class EchoVlm:
        def generate(self, prompt, image_path=None):
            return (
                "<<<TXT>>>\n"
                "1.\n分數：禁止\na/b\n2.\n指數：禁止\n"
                "12.\n禁止輸出「看起來像數學的純文字」\n"
                "<<<TEX>>>\n"
                "\\documentclass{ctexart}\\begin{document}"
                "分數：禁止\n指數：禁止\n禁止輸出「看起來像數學的純文字」"
                "\\end{document}"
            )

    txt, tex, warn = FinalPolisher(EchoVlm()).polish("真實題幹 $x=1$")
    assert "分數：禁止" not in txt
    assert "真實題幹" in txt
    assert "分數：禁止" not in tex
    assert any("math rules" in w for w in warn)


def test_looks_like_math_rules_echo():
    assert _looks_like_math_rules_echo("分數：禁止\n指數：禁止")
    assert not _looks_like_math_rules_echo("若 $x=1$，則下列何者正確？")
