"""Stage 3: stitch draft + VLM polish -> .txt / .tex."""

from __future__ import annotations

import re

from .latex_math import sanitize_tex_document, strip_model_junk
from .models import LayoutBlock
from .prompts import CONTENT_FIRST_POLISH_PROMPT


class DraftAssembler:
    def stitch(self, blocks: list[LayoutBlock]) -> str:
        parts = [
            b.raw_text.strip()
            for b in sorted(blocks, key=lambda x: (x.page, x.order))
            if b.raw_text.strip()
        ]
        return "\n\n".join(parts)


class FinalPolisher:
    """
    Arrange stage:
      draft -> VLM polish with forced LaTeX math -> .txt + .tex
    """

    def __init__(self, vlm):
        self.vlm = vlm

    @staticmethod
    def prompt_header() -> str:
        return CONTENT_FIRST_POLISH_PROMPT

    def polish(self, draft: str) -> tuple[str, str, list[str]]:
        """
        Returns (txt, tex, warnings).
        Warnings are short utility phrases for WarnCollector (no prefix).
        """
        warns: list[str] = []
        raw = self.vlm.generate(self.prompt_header() + draft, image_path=None)
        txt, tex, parse_warn = self._parse(raw, draft)
        if parse_warn:
            warns.append(parse_warn)
        txt = strip_model_junk(txt)
        tex = sanitize_tex_document(tex)
        if "\\documentclass" in tex and "\\end{document}" not in tex:
            warns.append("polish truncated; draft kept")
        return txt, tex, warns

    def _parse(self, raw: str, draft_fallback: str) -> tuple[str, str, str | None]:
        raw = strip_model_junk(raw)
        txt_m = re.search(r"<<<TXT>>>\s*(.*?)\s*<<<TEX>>>", raw, flags=re.DOTALL | re.IGNORECASE)
        tex_m = re.search(r"<<<TEX>>>\s*(.*)$", raw, flags=re.DOTALL | re.IGNORECASE)
        if txt_m and tex_m:
            return txt_m.group(1).strip(), tex_m.group(1).strip(), None

        extracted = self._extract_tex_document(raw)
        if extracted:
            return self.extract_tex_body(extracted), extracted, None

        return (
            (raw.strip() or draft_fallback.strip()),
            self.wrap_tex(draft_fallback),
            "polish parse fail; draft wrapped",
        )

    @staticmethod
    def _extract_tex_document(raw: str) -> str | None:
        """Recover \\documentclass...\\end{document} from prose/markdown wrappers."""
        fence = re.search(
            r"```(?:latex|tex)?\s*(\\documentclass.*?\\end\{document\})\s*```",
            raw,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if fence:
            return fence.group(1).strip()
        m = re.search(
            r"(\\documentclass.*?\\end\{document\})",
            raw,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def wrap_tex(body: str) -> str:
        return (
            "\\documentclass[12pt]{ctexart}\n"
            "\\usepackage{amsmath,amssymb,booktabs}\n"
            "\\usepackage{longtable,array}\n"
            "\\usepackage{geometry}\n"
            "\\geometry{margin=2.2cm}\n"
            "\\begin{document}\n\n"
            f"{body.strip()}\n\n"
            "\\end{document}\n"
        )

    @staticmethod
    def extract_tex_body(tex: str) -> str:
        """Pull content between \\begin{document}...\\end{document}; else return as-is."""
        m = re.search(
            r"\\begin\{document\}(.*)\\end\{document\}",
            tex,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()
        return tex.strip()
