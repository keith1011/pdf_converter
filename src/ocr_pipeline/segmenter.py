"""Stitch-then-segment: draft text → PageIR (content-first Ship 1)."""

from __future__ import annotations

import re

from .models import BBox, ContentSegment, IntegrityStatus, PageIR, SegmentKind

_META_LINE = re.compile(r"將圖片.*轉換")
_DOLLAR_MATH = re.compile(r"\$([^$]+)\$")
_HTML_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TABLE_DIVIDER_CELL = re.compile(r":?-{3,}:?")
_LAYOUT_ENV = re.compile(
    r"\\(begin|end)\{(itemize|enumerate|align\*?|aligned|gather\*?|equation\*?)\}"
)
_ITEM_PREFIX = re.compile(r"^\\item(?:\[[^\]]*\])?\s*")
_MARK_NOTE = re.compile(r"\d+\s*[MA](?:\s*\+\s*\d+\s*[MA])*", re.IGNORECASE)
_MATH_RELATION = re.compile(r"=|\\(?:le|ge|ne|approx)\b")
_TEX_MATH_HINT = re.compile(
    r"\\(?:frac|dfrac|tfrac|times|sqrt|angle|triangle|begin|sum|prod|int)\b|[\\^_]"
)


def _looks_like_math(text: str) -> bool:
    return bool(_TEX_MATH_HINT.search(text) or _MATH_RELATION.search(text))


def _linearized_lines(stitched_text: str) -> list[str]:
    """Remove Markdown table chrome and turn cells/HTML breaks into lines."""
    lines: list[str] = []
    active_env: str | None = None
    for raw_line in stitched_text.splitlines():
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
            for piece in _HTML_BREAK.split(chunk):
                piece = _ITEM_PREFIX.sub("", piece.strip())
                if active_env and not active_env.startswith(("itemize", "enumerate")):
                    piece = piece.lstrip("&").rstrip()
                    piece = re.sub(r"\\\\\s*$", "", piece).rstrip()
                lines.append(piece)
    return lines


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
                parts.append(
                    ContentSegment(
                        kind=SegmentKind.PROSE,
                        text=before,
                        source_block_id=source_id,
                        bbox=page_bbox,
                        integrity=IntegrityStatus.OK,
                    )
                )
            parts.append(
                ContentSegment(
                    kind=SegmentKind.MATH,
                    text=m.group(1).strip(),
                    source_block_id=source_id,
                    bbox=page_bbox,
                    integrity=IntegrityStatus.OK,
                )
            )
            pos = m.end()
        after = line[pos:].strip()
        if after:
            kind = SegmentKind.MATH if _looks_like_math(after) else SegmentKind.PROSE
            # Whole-line undelimited math (no $ found)
            if pos == 0 and kind is SegmentKind.MATH:
                parts = [
                    ContentSegment(
                        kind=SegmentKind.MATH,
                        text=after,
                        source_block_id=source_id,
                        bbox=page_bbox,
                        integrity=IntegrityStatus.OK,
                    )
                ]
            else:
                parts.append(
                    ContentSegment(
                        kind=kind,
                        text=after,
                        source_block_id=source_id,
                        bbox=page_bbox,
                        integrity=IntegrityStatus.OK,
                    )
                )
        if not parts and line:
            kind = SegmentKind.MATH if _looks_like_math(line) else SegmentKind.PROSE
            parts.append(
                ContentSegment(
                    kind=kind,
                    text=line,
                    source_block_id=source_id,
                    bbox=page_bbox,
                    integrity=IntegrityStatus.OK,
                )
            )
        segments.extend(parts)

    return PageIR(page_index=page_index, segments=segments)
