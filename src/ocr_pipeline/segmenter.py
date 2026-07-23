"""Stitch-then-segment: draft text → PageIR (content-first Ship 1)."""

from __future__ import annotations

import re

from .models import BBox, ContentSegment, IntegrityStatus, PageIR, SegmentKind

_META_LINE = re.compile(r"將圖片.*轉換")
# Allow \\$ (currency) inside math; do not treat it as a delimiter.
_DOLLAR_MATH = re.compile(r"(?<!\\)\$((?:[^$\\]|\\.)+?)(?<!\\)\$")
_HTML_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TABLE_DIVIDER_CELL = re.compile(r":?-{3,}:?")
_LAYOUT_ENV = re.compile(
    r"\\(begin|end)\{(itemize|enumerate|align\*?|aligned|gather\*?|equation\*?)\}"
)
_ITEM_PREFIX = re.compile(r"^\\item(?:\[[^\]]*\])?\s*")
_MARK_NOTE = re.compile(r"\d+\s*[MA](?:\s*\+\s*\d+\s*[MA])*", re.IGNORECASE)
_MATH_RELATION = re.compile(r"=|\\(?:le|ge|ne|approx)\b")
# Do NOT match bare \\begin — that classifies tabular/table as math and
# content_first wraps them as $...$ (Missing $, Misplaced \\noalign).
_TEX_MATH_HINT = re.compile(
    r"\\(?:frac|dfrac|tfrac|feac|fraq|times|tims|sqrt|angle|triangle|sum|prod|int)\b"
    r"|\\begin\{(?:matrix|pmatrix|bmatrix|vmatrix|Vmatrix|cases)\}"
    # Any other TeX control word except document/table chrome
    r"|\\(?!end\b|begin\b|hline\b|centering\b|documentclass\b|usepackage\b|"
    r"geometry\b|item\b|caption\b|label\b|ref\b|newpage\b|noindent\b)"
    r"[a-zA-Z]+\b"
    r"|[\^_]"
)
_TAB_ENV_BEGIN = re.compile(
    r"\\begin\{(table\*?|tabular\*?|longtable)\}(?:\[[^\]]*\])?(?:\{[^}]*\})?",
    re.IGNORECASE,
)
_TAB_ENV_END = re.compile(
    r"\\end\{(table\*?|tabular\*?|longtable)\}",
    re.IGNORECASE,
)
_HLINE = re.compile(r"\\hline\b")
_EMPTY_DOLLAR_PAIR = re.compile(r"\$[ \t]*\$")  # same-line only; do not cross \n
_TABULAR_CHROME_MATH = re.compile(
    r"^\\(?:begin|end)\{(?:table\*?|tabular\*?|longtable)\}"
    r"|^\\hline$"
    r"|^\|?[cclr@\{\}\s\*]*\|?$"
    r"|^\$+$",
    re.IGNORECASE,
)
_ROW_BREAK = re.compile(r"\\\\\s*")
_MD_FENCE = re.compile(r"```(?:\w+)?")
_CENTERING = re.compile(r"\\centering\b")
_BRACKET_DISPLAY = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_PAREN_INLINE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
_CJK_CHAR = re.compile(r"[\u4e00-\u9fff]")
_CJK_OR_PUNCT = re.compile(r"^[\u4e00-\u9fff\s，。、：；！？「」『』（）,.．；：、]+$")
_CASES_ENV = re.compile(
    r"\\begin\{cases\}.*?\\end\{cases\}",
    re.DOTALL | re.IGNORECASE,
)
# Marking-scheme OCR junk: \frac{正方形性質}{-} / \frac{-}{-}
_JUNK_FRAC_CJK = re.compile(
    r"\\(?:frac|dfrac|tfrac)\{[^}]*[\u4e00-\u9fff][^}]*\}\{[^}]*\}"
)
_JUNK_FRAC_DASH = re.compile(r"\\frac\{-\}\{-\}")
_TEXT_CJK = re.compile(r"\\text\{([^}]*[\u4e00-\u9fff][^}]*)\}")
_TEXT_PUNCT_ONLY = re.compile(r"\\text\{[\s，。、：；！？「」『』（）,.\-–—]*\}")
_LEADING_CJK_RUN = re.compile(r"^([\u4e00-\u9fff\s，。、：；！？「」『』（）,.．]+)")


def _looks_like_math(text: str) -> bool:
    if _TABULAR_CHROME_MATH.fullmatch(text.strip()):
        return False
    if _CJK_OR_PUNCT.fullmatch(text.strip()):
        return False
    return bool(_TEX_MATH_HINT.search(text) or _MATH_RELATION.search(text))


def _clean_math_body(text: str) -> str:
    """Drop stray $ / \\[ \\] \\( \\); keep \\$ currency."""
    text = text.replace(r"\[", " ").replace(r"\]", " ")
    text = text.replace(r"\(", " ").replace(r"\)", " ")
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] == "$":
            out.append("\\$")
            i += 2
            continue
        if text[i] == "$":
            i += 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out).strip()


def _strip_marking_junk_commands(text: str) -> str:
    """Remove OCR junk fracs; unwrap \\text{CJK} to plain prose."""
    text = _JUNK_FRAC_CJK.sub("", text)
    text = _JUNK_FRAC_DASH.sub("", text)
    text = _TEXT_PUNCT_ONLY.sub(" ", text)
    text = _TEXT_CJK.sub(r"\1", text)
    text = re.sub(r"\\caption(?:\[[^\]]*\])?\{[^}]*\}", "", text, flags=re.IGNORECASE)
    return text.strip()


def _first_cjk_outside_braces(text: str) -> int | None:
    """Index of first CJK character not inside {...} (so we don't split \\frac)."""
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        elif depth == 0 and _CJK_CHAR.match(c):
            return i
        i += 1
    return None


def _emit_tail_after_cjk(after: str) -> list[tuple[SegmentKind, str]]:
    """Peel leading CJK, then keep TeX-command tails as math."""
    after = _strip_marking_junk_commands(after)
    if not after:
        return []
    parts: list[tuple[SegmentKind, str]] = []
    lead = _LEADING_CJK_RUN.match(after)
    if lead:
        prose = lead.group(1).strip()
        if prose:
            parts.append((SegmentKind.PROSE, prose))
        after = after[lead.end() :].strip()
    if not after:
        return parts
    if _looks_like_math(after) or re.search(r"\\[a-zA-Z]+\b", after):
        # Still has CJK inside braces of math — keep as math only if no free CJK
        if _first_cjk_outside_braces(after) is None:
            parts.append((SegmentKind.MATH, after))
        else:
            parts.append((SegmentKind.PROSE, after))
    else:
        parts.append((SegmentKind.PROSE, after))
    return parts


def _partition_math_and_prose(text: str) -> list[tuple[SegmentKind, str]]:
    """Split mixed 'math + Chinese' blobs so CJK is never inside $...$."""
    text = _strip_marking_junk_commands(_clean_math_body(text))
    if not text:
        return []
    # Any remaining CJK inside TeX args → treat carefully via tail emit
    if _CJK_CHAR.search(text) and (
        r"\frac" in text or r"\dfrac" in text or r"\tfrac" in text
    ):
        return [(SegmentKind.PROSE, text)]

    idx = _first_cjk_outside_braces(text)
    if idx is None:
        kind = SegmentKind.MATH if _looks_like_math(text) else SegmentKind.PROSE
        return [(kind, text)]
    before = text[:idx].strip()
    after = text[idx:].strip()
    parts: list[tuple[SegmentKind, str]] = []
    if before:
        kind = SegmentKind.MATH if _looks_like_math(before) else SegmentKind.PROSE
        parts.append((kind, before))
    parts.extend(_emit_tail_after_cjk(after))
    return parts


def _normalize_math_delimiters(text: str) -> str:
    """Content-first uses single $...$; collapse \\[ \\] / \\( \\) / $$."""
    text = _BRACKET_DISPLAY.sub(lambda m: f"${m.group(1).strip()}$", text)
    text = _PAREN_INLINE.sub(lambda m: f"${m.group(1).strip()}$", text)
    # Flatten cases env to inline (avoid \\ begin/end inside $)
    text = _CASES_ENV.sub(
        lambda m: "$" + m.group(0).replace(r"\\", " ").strip() + "$",
        text,
    )
    return text.replace("$$", "$")


def _explode_tabular_chrome(text: str) -> str:
    """Turn LaTeX table chrome into newlines so cells can be linearized."""
    text = _TAB_ENV_BEGIN.sub("\n", text)
    text = _TAB_ENV_END.sub("\n", text)
    text = _HLINE.sub("\n", text)
    text = _CENTERING.sub("\n", text)
    text = _MD_FENCE.sub("\n", text)
    # Content-first: collapse display $$ before pair extraction
    text = _normalize_math_delimiters(text)
    # Same-line empty $ $ only (never eat closing+opening across lines)
    text = _EMPTY_DOLLAR_PAIR.sub("\n", text)
    return text


def _split_ampersand_rows(chunk: str) -> list[str]:
    """Split residual tabular rows (`\\\\`) and cells (`&`) into lines."""
    if "&" not in chunk and r"\\" not in chunk:
        return [chunk]
    if "&" not in chunk:
        # Lone \\\\ without &: keep as-is (math may use \\\\ only inside envs
        # already stripped). Still flatten trailing row breaks.
        cleaned = _ROW_BREAK.sub("\n", chunk)
        return [cleaned] if "\n" not in cleaned else cleaned.splitlines()

    rows = _ROW_BREAK.split(chunk)
    cells: list[str] = []
    for row in rows:
        row = row.strip()
        if not row:
            continue
        if "&" in row:
            cells.extend(cell.strip() for cell in row.split("&") if cell.strip())
        else:
            cells.append(row)
    return cells


def _linearized_lines(stitched_text: str) -> list[str]:
    """Remove Markdown/LaTeX table chrome and turn cells/HTML breaks into lines."""
    text = _explode_tabular_chrome(stitched_text)
    lines: list[str] = []
    active_env: str | None = None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        env_match = _LAYOUT_ENV.fullmatch(stripped)
        if env_match:
            active_env = env_match.group(2) if env_match.group(1) == "begin" else None
            continue

        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 3:
            cells = [cell.strip() for cell in stripped[1:-1].split("|")]
            if cells and all(
                not cell or _TABLE_DIVIDER_CELL.fullmatch(cell) for cell in cells
            ):
                continue
            chunks = cells
        else:
            chunks = [raw_line]

        for chunk in chunks:
            for amp_piece in _split_ampersand_rows(chunk):
                for piece in _HTML_BREAK.split(amp_piece):
                    piece = _ITEM_PREFIX.sub("", piece.strip())
                    if active_env and not active_env.startswith(("itemize", "enumerate")):
                        piece = piece.lstrip("&").rstrip()
                        piece = re.sub(r"\\\\\s*$", "", piece).rstrip()
                    if piece:
                        lines.append(piece)
    return lines


def _is_tabular_chrome_body(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if _TABULAR_CHROME_MATH.fullmatch(t):
        return True
    if _TAB_ENV_BEGIN.search(t) or _TAB_ENV_END.search(t) or _HLINE.search(t):
        return True
    # Model sometimes emits a mid-body \end{document} / empty \caption
    if re.fullmatch(r"\\(?:begin|end)\{document\}", t, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"\\caption(?:\[[^\]]*\])?\{[^}]*\}", t, flags=re.IGNORECASE):
        return True
    return False


def _strip_orphan_dollars(text: str) -> str:
    """Remove stray wrapping $ so render does not emit $$...$."""
    t = text.strip()
    while t.startswith("$"):
        t = t[1:].lstrip()
    while t.endswith("$") and not t.endswith(r"\$"):
        t = t[:-1].rstrip()
    return t.strip()


def _append_partitions(
    parts: list[ContentSegment],
    text: str,
    *,
    source_id: str,
    page_bbox: BBox,
) -> None:
    for kind, body in _partition_math_and_prose(text):
        if not body or _is_tabular_chrome_body(body):
            continue
        parts.append(
            ContentSegment(
                kind=kind,
                text=body,
                source_block_id=source_id,
                bbox=page_bbox,
                integrity=IntegrityStatus.OK,
            )
        )


def segment_stitched_page(
    *,
    page_index: int,
    stitched_text: str,
    page_bbox: BBox,
) -> PageIR:
    """
    Segment a stitched page draft into PageIR.

    Ship 1 (3B/6A): all segments share `p{N}_stitched` and the full-page bbox.
    """
    source_id = f"p{page_index}_stitched"
    segments: list[ContentSegment] = []

    for raw_line in _linearized_lines(stitched_text):
        line = raw_line.strip()
        if not line:
            continue
        if _META_LINE.search(line):
            continue
        if _MARK_NOTE.fullmatch(line):
            segments.append(
                ContentSegment(
                    kind=SegmentKind.MARK_NOTE,
                    text=line,
                    source_block_id=source_id,
                    bbox=page_bbox,
                    integrity=IntegrityStatus.OK,
                )
            )
            continue

        parts: list[ContentSegment] = []
        pos = 0
        for m in _DOLLAR_MATH.finditer(line):
            before = line[pos : m.start()].strip()
            if before:
                _append_partitions(
                    parts, before, source_id=source_id, page_bbox=page_bbox
                )
            math_body = _strip_orphan_dollars(m.group(1))
            if math_body and not _is_tabular_chrome_body(math_body):
                _append_partitions(
                    parts, math_body, source_id=source_id, page_bbox=page_bbox
                )
            pos = m.end()
        after = _strip_orphan_dollars(line[pos:])
        if after and not _is_tabular_chrome_body(after):
            if pos == 0:
                parts = []
            _append_partitions(parts, after, source_id=source_id, page_bbox=page_bbox)
        if not parts and line:
            cleaned = _strip_orphan_dollars(line)
            if cleaned and not _is_tabular_chrome_body(cleaned):
                _append_partitions(
                    parts, cleaned, source_id=source_id, page_bbox=page_bbox
                )
        segments.extend(parts)

    return PageIR(page_index=page_index, segments=segments)
