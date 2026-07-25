"""Stage 3: stitch draft + VLM polish -> .txt / .tex."""

from __future__ import annotations

import re

from .latex_math import sanitize_tex_document, strip_model_junk
from .models import LayoutBlock
from .prompts import CONTENT_FIRST_POLISH_PROMPT

_OPTION_ONLY = re.compile(r"^[A-Da-d][\.．、)]\s*$")
_PUNCT_ONLY = re.compile(r"^[。．.、，,；;：:！!？?\s]+$")
_OPTION_START = re.compile(r"^[A-Da-d][\.．、)]\s*")
_NUP_SPLIT = re.compile(r"(<<<nup:(?:v\d+|zh|en|[A-Za-z0-9_\-]+)>>>)")


def coalesce_stitched_fragments(parts: list[str]) -> str:
    """
    Glue MinerU/VLM atomized MCQ fragments before blank-line join.

    Example: ``A.`` + ``-1`` + ``。`` → one chunk ``A. -1。``
    """
    if not parts:
        return ""
    merged: list[str] = [parts[0].strip()]
    for raw in parts[1:]:
        cur = raw.strip()
        if not cur:
            continue
        prev = merged[-1]
        if _should_glue_fragments(prev, cur):
            if _PUNCT_ONLY.match(cur):
                merged[-1] = prev.rstrip() + cur.strip()
            elif _OPTION_ONLY.match(prev):
                merged[-1] = f"{prev.rstrip()} {cur.lstrip()}".strip()
            else:
                merged[-1] = f"{prev.rstrip()} {cur.lstrip()}".strip()
        else:
            merged.append(cur)
    return "\n\n".join(merged)


def _should_glue_fragments(prev: str, cur: str) -> bool:
    if _OPTION_ONLY.match(cur):
        return False  # new option starts a chunk
    if re.match(r"^\d{1,2}[\.．]\s*$", cur) or re.match(r"^\d{1,2}[\.．]\s*$", prev):
        return False
    if _PUNCT_ONLY.match(cur):
        return True
    if _OPTION_ONLY.match(prev) and len(cur) <= 80:
        return True
    # Keep gluing within an open option line (A. … 或 -4。)
    if (
        _OPTION_START.match(prev)
        and not _OPTION_ONLY.match(cur)
        and len(cur) <= 48
        and len(prev) <= 120
    ):
        return True
    return len(prev) <= 4 and len(cur) <= 4 and not cur[:1].isdigit()


class DraftAssembler:
    def stitch(self, blocks: list[LayoutBlock]) -> str:
        parts: list[str] = []
        prev_vid: str | None = None
        for b in sorted(blocks, key=lambda x: (x.page, x.order)):
            text = b.raw_text.strip()
            if not text:
                continue
            vid = b.meta.get("version_id")
            if isinstance(vid, str) and vid and vid != prev_vid:
                parts.append(f"<<<nup:{vid}>>>")
                prev_vid = vid
            parts.append(text)
        return coalesce_stitched_fragments(parts)


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

        When draft contains ``<<<nup:…>>>`` markers, polish each version chunk
        separately and re-insert markers so PageIR can keep ``version_id``.
        """
        if _NUP_SPLIT.search(draft):
            return self._polish_nup_chunks(draft)
        return self._polish_once(draft)

    def _polish_once(self, draft: str) -> tuple[str, str, list[str]]:
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

    def _polish_nup_chunks(self, draft: str) -> tuple[str, str, list[str]]:
        parts = _NUP_SPLIT.split(draft)
        txt_out: list[str] = []
        body_out: list[str] = []
        warns: list[str] = []
        for part in parts:
            chunk = part.strip()
            if not chunk:
                continue
            if chunk.startswith("<<<nup:") and chunk.endswith(">>>"):
                txt_out.append(chunk)
                body_out.append(chunk)
                continue
            t, x, w = self._polish_once(chunk)
            warns.extend(w)
            txt_out.append(t.strip())
            body_out.append(self.extract_tex_body(x).strip() or t.strip())
        txt = "\n\n".join(txt_out)
        tex = sanitize_tex_document(self.wrap_tex("\n\n".join(body_out)))
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
