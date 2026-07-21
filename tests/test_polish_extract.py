"""Recover TeX when VLM wraps output in markdown / prose."""

from __future__ import annotations

from ocr_pipeline.assemble import FinalPolisher


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


def test_parse_uses_extracted_document():
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
    assert warn and any("extracted" in w for w in ([warn] if isinstance(warn, str) else warn))
