"""Stage 3: stitch draft + VLM polish -> .txt / .tex."""

from __future__ import annotations

import re

from opencc import OpenCC

from .latex_math import sanitize_tex_document, strip_model_junk
from .models import LayoutBlock
from .prompts import CONTENT_FIRST_POLISH_PROMPT, MCQ_POLISH_PROMPT
from .pylatex_assist import encode_unicode_outside_math

_OPTION_ONLY = re.compile(r"^[A-Da-d][\.．、)]\s*$")
_PUNCT_ONLY = re.compile(r"^[。．.、，,；;：:！!？?\s]+$")
_OPTION_START = re.compile(r"^[A-Da-d][\.．、)]\s*")
_NUP_SPLIT = re.compile(r"(<<<nup:(?:v\d+|zh|en|[A-Za-z0-9_\-]+)>>>)")
_QID_OPENER = re.compile(r"^(\d{1,2})[\.．]\s*")
# Only split before a new stem opener — blank lines inside one MCQ (stem↔A–D) must not cut.
_Q_CHUNK_SPLIT = re.compile(r"\n{2,}(?=\d{1,2}[\.．])")


# Markers from prompts.LATEX_MATH_RULES — VLM sometimes copies these into the body.
_MATH_RULES_ECHO_MARKERS = (
    "分數：禁止",
    "指數：禁止",
    "禁止輸出「看起來像數學的純文字」",
)

# Stage3 for MCQ: default keep Stage2 crop text (no VLM rewrite).
_MCQ_STAGE3_SANITIZE = "sanitize"
_MCQ_STAGE3_PADDLE_SANITIZE = "paddle_sanitize"
_MCQ_STAGE3_VLM = "vlm"
_S2HK_CONVERTER = OpenCC("s2hk")


def _looks_like_math_rules_echo(text: str) -> bool:
    """True when polish output is mostly the injected math-rules prompt."""
    if not text:
        return False
    hits = sum(1 for marker in _MATH_RULES_ECHO_MARKERS if marker in text)
    return hits >= 2


def format_mcq_question_text(raw: str, question_id: int) -> str:
    """Ensure MCQ body starts with ``{qid}.`` so emit/polish keep question boundaries."""
    text = (raw or "").strip()
    if not text:
        return f"{question_id}."
    m = _QID_OPENER.match(text)
    if m and int(m.group(1)) == int(question_id):
        return text
    if m:
        # Wrong/missing opener from OCR — replace leading number with meta qid.
        text = text[m.end() :].lstrip()
    return f"{question_id}. {text}"


def split_question_chunks(draft: str) -> list[str]:
    """Split a stitched draft into per-question chunks.

    Splits only on blank lines that *precede a stem opener* ``N.``. Blank lines
    between stem and A–D (common VLM formatting) must not create orphan chunks,
    or jsonl mapping keeps stem-only and drops options.
    """
    text = (draft or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in _Q_CHUNK_SPLIT.split(text) if p.strip()]
    if len(parts) <= 1:
        return parts
    numbered = sum(1 for p in parts if _QID_OPENER.match(p))
    if numbered >= 2:
        return parts
    return [text]


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
    if _QID_OPENER.match(cur):
        return False  # never glue a new stem onto previous fragment
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
        """
        Join block OCR texts.

        When blocks carry ``meta.question_id`` (DSE MCQ layout), emit one chunk
        per question with a ``{qid}.`` opener and a blank line between questions.
        Do **not** coalesce across those question boundaries (that caused glued MCQs).
        """
        ordered = sorted(blocks, key=lambda x: (x.page, x.order))
        nonempty = [b for b in ordered if (b.raw_text or "").strip()]
        mcq_blocks = [
            b for b in nonempty if isinstance(b.meta.get("question_id"), int)
        ]
        if mcq_blocks and len(mcq_blocks) == len(nonempty):
            chunks: list[str] = []
            prev_vid: str | None = None
            for b in mcq_blocks:
                vid = b.meta.get("version_id")
                if isinstance(vid, str) and vid and vid != prev_vid:
                    chunks.append(f"<<<nup:{vid}>>>")
                    prev_vid = vid
                qid = int(b.meta["question_id"])
                chunks.append(format_mcq_question_text(b.raw_text, qid))
            return "\n\n".join(chunks)

        parts: list[str] = []
        prev_vid = None
        for b in ordered:
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
      draft -> VLM polish with forced LaTeX math -> .txt / .tex

    For DSE MCQ (``question_id`` pages / multi-``N.`` drafts), default Stage3 is
    **light sanitize** of Stage2 crop text (no VLM rewrite). Set
    ``mcq_stage3="vlm"`` to use ``MCQ_POLISH_PROMPT`` instead.
    """

    def __init__(self, vlm, *, mcq_stage3: str = _MCQ_STAGE3_SANITIZE):
        self.vlm = vlm
        mode = (mcq_stage3 or _MCQ_STAGE3_SANITIZE).strip().lower()
        if mode not in {
            _MCQ_STAGE3_SANITIZE,
            _MCQ_STAGE3_PADDLE_SANITIZE,
            _MCQ_STAGE3_VLM,
        }:
            mode = _MCQ_STAGE3_SANITIZE
        self.mcq_stage3 = mode

    @staticmethod
    def prompt_header() -> str:
        return CONTENT_FIRST_POLISH_PROMPT

    @staticmethod
    def mcq_prompt_header() -> str:
        return MCQ_POLISH_PROMPT

    def polish(self, draft: str) -> tuple[str, str, list[str]]:
        """
        Returns (txt, tex, warnings).
        Warnings are short utility phrases for WarnCollector (no prefix).

        When draft contains ``<<<nup:…>>>`` markers, polish each version chunk
        separately and re-insert markers so PageIR can keep ``version_id``.

        Multi-question drafts (blank-line separated ``N.`` stems) take the MCQ
        Stage3 path (sanitize by default).

        Blank drafts skip the VLM call: otherwise the model often echoes
        ``LATEX_MATH_RULES`` from the prompt into the document body.
        """
        if not (draft or "").strip():
            return "", self.wrap_tex(""), []
        if _NUP_SPLIT.search(draft):
            return self._polish_nup_chunks(draft)
        chunks = split_question_chunks(draft)
        if len(chunks) >= 2:
            return self.polish_mcq(draft)
        return self._polish_once(draft, prompt=self.prompt_header())

    def polish_mcq(self, draft: str) -> tuple[str, str, list[str]]:
        """MCQ arrange: keep Stage2 text (sanitize) or optional fidelity VLM polish."""
        if not (draft or "").strip():
            return "", self.wrap_tex(""), []
        if self.mcq_stage3 == _MCQ_STAGE3_VLM:
            chunks = split_question_chunks(draft)
            if len(chunks) >= 2:
                return self._polish_question_chunks(chunks, prompt=self.mcq_prompt_header())
            return self._polish_once(draft, prompt=self.mcq_prompt_header())
        if self.mcq_stage3 == _MCQ_STAGE3_PADDLE_SANITIZE:
            return self._sanitize_paddle_mcq_draft(draft)
        return self._sanitize_mcq_draft(draft)

    def _sanitize_paddle_mcq_draft(self, draft: str) -> tuple[str, str, list[str]]:
        """Re-render Paddle MCQ markdown deterministically; never call a VLM."""
        from .mcq_structured import parse_stage2_text, render_text

        warns = [
            "mcq stage3 paddle sanitize "
            "(deterministic five-line render + OpenCC s2hk)"
        ]
        rendered: list[str] = []
        for chunk in split_question_chunks(strip_model_junk((draft or "").strip())):
            match = _QID_OPENER.match(chunk)
            if match is None:
                rendered.append(chunk.strip())
                warns.append("paddle sanitize kept unnumbered chunk")
                continue
            try:
                result = parse_stage2_text(chunk)
                rendered.append(render_text(int(match.group(1)), result))
            except ValueError:
                rendered.append(chunk.strip())
                warns.append(f"paddle sanitize kept invalid Q{match.group(1)}")
        body = _S2HK_CONVERTER.convert("\n\n".join(rendered))
        body = encode_unicode_outside_math(body)
        return body, sanitize_tex_document(self.wrap_tex(body)), warns

    def _sanitize_mcq_draft(self, draft: str) -> tuple[str, str, list[str]]:
        """Deterministic Stage3 for MCQ: strip junk + pylatexenc; no VLM."""
        warns = ["mcq stage3 sanitize (stage2 text kept)"]
        body = strip_model_junk((draft or "").strip())
        chunks = split_question_chunks(body)
        if len(chunks) >= 2:
            body = "\n\n".join(
                encode_unicode_outside_math(c.strip()) for c in chunks if c.strip()
            )
        else:
            body = encode_unicode_outside_math(body)
        txt = body
        tex = sanitize_tex_document(self.wrap_tex(body))
        return txt, tex, warns

    def _polish_question_chunks(
        self, chunks: list[str], *, prompt: str | None = None
    ) -> tuple[str, str, list[str]]:
        header = prompt or self.mcq_prompt_header()
        txt_out: list[str] = []
        body_out: list[str] = []
        warns: list[str] = []
        for chunk in chunks:
            t, x, w = self._polish_once(chunk, prompt=header)
            warns.extend(w)
            txt_out.append(t.strip())
            body_out.append(self.extract_tex_body(x).strip() or t.strip())
        txt = "\n\n".join(txt_out)
        tex = sanitize_tex_document(self.wrap_tex("\n\n".join(body_out)))
        return txt, tex, warns

    def _polish_once(
        self, draft: str, *, prompt: str | None = None
    ) -> tuple[str, str, list[str]]:
        warns: list[str] = []
        header = prompt or self.prompt_header()
        raw = self.vlm.generate(header + draft, image_path=None)
        txt, tex, parse_warn = self._parse(raw, draft)
        if parse_warn:
            warns.append(parse_warn)
        txt = strip_model_junk(txt)
        tex = sanitize_tex_document(tex)
        # Deterministic Unicode→LaTeX assist (pylatexenc) after VLM rewrite.
        # Context7 /phfaist/pylatexenc: unknown_char_policy='keep' for CJK.
        txt = encode_unicode_outside_math(txt)
        body = encode_unicode_outside_math(self.extract_tex_body(tex))
        tex = sanitize_tex_document(self.wrap_tex(body)) if body else tex
        if "\\documentclass" in tex and "\\end{document}" not in tex:
            warns.append("polish truncated; draft kept")
        if _looks_like_math_rules_echo(txt) or _looks_like_math_rules_echo(
            self.extract_tex_body(tex)
        ):
            warns.append("polish echoed math rules; draft kept")
            kept = encode_unicode_outside_math(draft.strip())
            return kept, sanitize_tex_document(self.wrap_tex(kept)), warns
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
