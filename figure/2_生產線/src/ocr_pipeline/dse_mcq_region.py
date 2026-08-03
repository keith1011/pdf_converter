"""DSE Paper2 MCQ region rules: tag OCR lines and pair stem→A–D spans."""

from __future__ import annotations

import re

from .dse_mcq_profile import McqProfile
from .dse_mcq_types import LineKind, McqAnchors, McqRegion, OcrLine, TaggedLine

_OPTION_KIND = {
    "A": LineKind.OPTION_A,
    "B": LineKind.OPTION_B,
    "C": LineKind.OPTION_C,
    "D": LineKind.OPTION_D,
}

_OPTION_KINDS = frozenset(_OPTION_KIND.values())


def _left_biased(line: OcrLine, profile: McqProfile) -> bool:
    limit = line.page_width * profile.left_bias_ratio
    return line.bbox[0] <= limit


_STEM_TOKEN = re.compile(r"^\s*(\d{1,2})[.．]")
_STEM_PAREN_TOKEN = re.compile(r"^\s*\((\d{1,2})\)")


def _match_stem_id(text: str, profile: McqProfile) -> int | None:
    for pat in profile.stem_opener_patterns:
        m = pat.match(text)
        if not m:
            continue
        qid = int(m.group(1))
        if qid < profile.question_id_min or qid > profile.question_id_max:
            return None
        # Character immediately after the opener token (dot / closing paren),
        # not after pattern-consumed trailing whitespace.
        token = _STEM_TOKEN.match(text) or _STEM_PAREN_TOKEN.match(text)
        if token is None:
            return None
        rest = text[token.end() :]
        # Reject decimals like "1.5…" for single-digit openers; allow glued
        # multi-digit stems such as OCR "33.11+26…".
        if rest[:1].isdigit() and qid < 10:
            return None
        # Reject OCR junk glued to the opener: "2.xs" (misread 2x^5).
        # Allow "1. Find…" (space then Latin) and "11．設…".
        if rest and not rest[0].isspace():
            ch0 = rest[0]
            if ch0.isascii() and ch0.isalpha():
                return None
        return qid
    return None


def _match_option_letter(text: str, profile: McqProfile) -> str | None:
    for pat in profile.option_patterns:
        m = pat.match(text)
        if not m:
            continue
        # First alphabetic A–D in the matched prefix
        head = m.group(0)
        for ch in head:
            if ch.upper() in _OPTION_KIND:
                return ch.upper()
        # Fallback: search whole match for letter group
        letter_m = re.search(r"[A-D]", head, flags=re.IGNORECASE)
        if letter_m:
            return letter_m.group(0).upper()
    return None


def tag_lines(lines: list[OcrLine], profile: McqProfile) -> list[TaggedLine]:
    tagged: list[TaggedLine] = []
    for line in lines:
        kind = LineKind.OTHER
        qid: int | None = None
        # Stem openers stay left-biased (avoids mid-column decimals / roman crumbs).
        # Option letters may sit in a 2×2 graph grid (B/D on the right) — no left bias.
        if _left_biased(line, profile):
            qid = _match_stem_id(line.text, profile)
            if qid is not None:
                kind = LineKind.STEM_CANDIDATE
        if kind is LineKind.OTHER:
            letter = _match_option_letter(line.text, profile)
            if letter is not None:
                kind = _OPTION_KIND[letter]
        tagged.append(TaggedLine(line=line, kind=kind, question_id=qid))
    return tagged


def _union_bbox(
    boxes: list[tuple[float, float, float, float]],
    *,
    pad: float,
    page_w: float,
    page_h: float,
) -> tuple[float, float, float, float]:
    x1 = min(b[0] for b in boxes) - pad
    y1 = min(b[1] for b in boxes) - pad
    x2 = max(b[2] for b in boxes) + pad
    y2 = max(b[3] for b in boxes) + pad
    return (
        max(0.0, x1),
        max(0.0, y1),
        min(page_w, x2),
        min(page_h, y2),
    )


def _anchors_from_kinds(kinds: list[LineKind]) -> McqAnchors:
    return McqAnchors(
        A=LineKind.OPTION_A in kinds,
        B=LineKind.OPTION_B in kinds,
        C=LineKind.OPTION_C in kinds,
        D=LineKind.OPTION_D in kinds,
    )


def _close_index(tagged: list[TaggedLine], start: int, end_exclusive: int) -> int:
    """Prefer close after option D, including same-row option values."""
    d_idx: int | None = None
    for j in range(start, end_exclusive):
        if tagged[j].kind is LineKind.OPTION_D:
            d_idx = j
            break
    if d_idx is None:
        return end_exclusive

    d_y1, d_y2 = tagged[d_idx].line.bbox[1], tagged[d_idx].line.bbox[3]
    band = max(40.0, d_y2 - d_y1)
    close = d_idx + 1
    for j in range(d_idx + 1, end_exclusive):
        if tagged[j].kind is not LineKind.OTHER:
            break
        y1 = tagged[j].line.bbox[1]
        if abs(y1 - d_y1) <= band:
            close = j + 1
        else:
            break
    return close


def _build_region(
    tagged: list[TaggedLine],
    *,
    stem_at: int,
    member_start: int,
    close_at: int,
    profile: McqProfile,
    page_w: float,
    page_h: float,
    question_id: int | None = None,
    orphan: bool = False,
) -> McqRegion | None:
    qid = question_id if question_id is not None else tagged[stem_at].question_id
    if qid is None:
        return None
    start = min(max(0, member_start), stem_at)
    member_idx = list(range(start, close_at))
    if not member_idx:
        return None
    kinds = [tagged[i].kind for i in member_idx]
    anchors = _anchors_from_kinds(kinds)
    boxes = [tagged[i].line.bbox for i in member_idx]
    bbox = _union_bbox(boxes, pad=profile.pad_px, page_w=page_w, page_h=page_h)
    x1, y1, x2, y2 = bbox
    if orphan:
        stem_x1 = [
            item.line.bbox[0]
            for item in tagged
            if item.kind is LineKind.STEM_CANDIDATE
        ]
        if stem_x1:
            x1 = min(x1, max(0.0, min(stem_x1) - profile.pad_px))
    # Widen to content column so diagrams on the right are not clipped.
    x2 = max(x2, min(page_w, page_w * profile.content_x_max_ratio))
    # Diagrams often hang slightly past the last option line.
    y2 = min(page_h, y2 + profile.below_options_pad_px)
    bbox = (x1, y1, x2, y2)
    return McqRegion(
        question_id=qid,
        bbox=bbox,
        anchors=anchors,
        incomplete=anchors.hit_count < profile.min_option_hits,
        line_indices=member_idx,
        orphan=orphan,
    )


def _filter_increasing_stems(
    tagged: list[TaggedLine], stem_indices: list[int], profile: McqProfile
) -> list[int]:
    if not profile.require_increasing_ids:
        return stem_indices

    # A Roman numeral inside a stem can be OCR'd as a larger Arabic qid
    # (2020 Q8: ``II.`` -> ``11.``).  Greedy filtering then discards the real
    # Q9/Q10 that follow.  Keep the longest increasing subsequence instead.
    paths: list[list[int]] = []
    for idx in stem_indices:
        qid = tagged[idx].question_id
        if qid is None:
            continue
        prior = [
            path
            for path in paths
            if (prior_qid := tagged[path[-1]].question_id) is not None
            and prior_qid < qid
        ]
        best_prior = max(prior, key=len, default=[])
        paths.append([*best_prior, idx])
    return max(paths, key=len, default=[])


def _option_run_bounds(
    tagged: list[TaggedLine], start: int, end_exclusive: int
) -> tuple[int, int] | None:
    """Return [first_option, after_D_same_row) inside [start, end) if enough options."""
    first: int | None = None
    for i in range(start, end_exclusive):
        if tagged[i].kind in _OPTION_KINDS:
            first = i
            break
    if first is None:
        return None
    close = _close_index(tagged, first, end_exclusive)
    kinds = [tagged[i].kind for i in range(first, close)]
    anchors = _anchors_from_kinds(kinds)
    if anchors.hit_count < 3:
        return None
    return first, close


def _leading_orphan_start(tagged: list[TaggedLine], first_option: int) -> int:
    """Skip DSE page-2 instructions/section title before a recovered Q1."""
    start = 0
    for i in range(first_option):
        if tagged[i].line.text.strip() in {"甲部", "乙部"}:
            start = i + 1
    return start


def _recover_orphan_options(
    tagged: list[TaggedLine],
    regions: list[McqRegion],
    *,
    profile: McqProfile,
    page_w: float,
    page_h: float,
) -> list[McqRegion]:
    """If A–D appear with no stem (OCR missed '18.'), invent qid = prev+1."""
    if not profile.recover_orphan_options or not regions:
        return regions

    covered: set[int] = set()
    for r in regions:
        covered.update(r.line_indices)

    out = list(regions)
    sorted_regions = sorted(out, key=lambda r: min(r.line_indices) if r.line_indices else 0)

    # The first question on a page frequently loses only its qid in light OCR.
    # Infer it from the next accepted qid and a complete A-D run in the prefix.
    first = sorted_regions[0]
    prefix_end = min(first.line_indices) if first.line_indices else 0
    prefix_bounds = _option_run_bounds(tagged, 0, prefix_end)
    leading_qid = first.question_id - 1
    if (
        prefix_bounds is not None
        and leading_qid >= profile.question_id_min
        and leading_qid <= profile.question_id_max
    ):
        first_opt, close_at = prefix_bounds
        member_start = _leading_orphan_start(tagged, first_opt)
        orphan = _build_region(
            tagged,
            stem_at=first_opt,
            member_start=member_start,
            close_at=close_at,
            profile=profile,
            page_w=page_w,
            page_h=page_h,
            question_id=leading_qid,
            orphan=True,
        )
        if orphan is not None and not orphan.incomplete:
            x1, y1, x2, y2 = orphan.bbox
            top_floor = 0.0
            if member_start > 0:
                top_floor = tagged[member_start - 1].line.bbox[3] + profile.pad_px
            orphan.bbox = (
                x1,
                max(top_floor, y1 - profile.leading_orphan_top_pad_px),
                x2,
                y2,
            )
            sorted_regions.insert(0, orphan)
            covered.update(orphan.line_indices)

    # Walk gaps between accepted regions (and after the last).
    recovered: list[McqRegion] = []
    for i, r in enumerate(sorted_regions):
        recovered.append(r)
        gap_start = max(r.line_indices) + 1 if r.line_indices else 0
        gap_end = (
            min(sorted_regions[i + 1].line_indices)
            if i + 1 < len(sorted_regions) and sorted_regions[i + 1].line_indices
            else len(tagged)
        )
        # skip lines already covered
        search_from = gap_start
        while search_from < gap_end:
            bounds = _option_run_bounds(tagged, search_from, gap_end)
            if bounds is None:
                break
            first_opt, close_at = bounds
            # ensure this run isn't already covered
            if any(j in covered for j in range(first_opt, close_at)):
                search_from = close_at
                continue
            qid = r.question_id + 1
            if qid < profile.question_id_min or qid > profile.question_id_max:
                break
            # avoid colliding with next known id
            if i + 1 < len(sorted_regions) and qid >= sorted_regions[i + 1].question_id:
                break
            orphan = _build_region(
                tagged,
                stem_at=first_opt,
                member_start=gap_start,
                close_at=close_at,
                profile=profile,
                page_w=page_w,
                page_h=page_h,
                question_id=qid,
                orphan=True,
            )
            if orphan is None or orphan.incomplete:
                search_from = close_at
                continue
            recovered.append(orphan)
            covered.update(orphan.line_indices)
            # chain: next orphan after this one may be prev+2
            r = orphan
            gap_start = close_at
            search_from = close_at
    return sorted(recovered, key=lambda x: x.bbox[1])


def _looks_like_stem_preamble(text: str) -> bool:
    """Reject short figure crumbs (axis labels, lone B/D) from stem preamble."""
    t = text.strip()
    if len(t) >= 10:
        return True
    return any("\u4e00" <= c <= "\u9fff" for c in t) and len(t) >= 4


def _preamble_start(
    tagged: list[TaggedLine], stem_at: int, prev_close: int, profile: McqProfile
) -> int:
    """Include nearby stem-prose above the opener; do not swallow figure crumbs / A–D."""
    start = stem_at
    stem_line = tagged[stem_at].line
    stem_y1, stem_y2 = stem_line.bbox[1], stem_line.bbox[3]
    i = stem_at - 1
    while i >= prev_close:
        kind = tagged[i].kind
        if kind in _OPTION_KINDS or kind is LineKind.STEM_CANDIDATE:
            break
        line = tagged[i].line
        if stem_y1 - line.bbox[3] > profile.preamble_max_gap_px:
            break
        if line.bbox[1] <= stem_y2 and line.bbox[3] >= stem_y1:
            start = i
            i -= 1
            continue
        if not _looks_like_stem_preamble(line.text):
            break
        start = i
        i -= 1
    return start


def detect_mcq_regions(lines: list[OcrLine], profile: McqProfile) -> list[McqRegion]:
    """Pair stem openers with A–D anchors into one region per question."""
    if not lines:
        return []

    tagged = tag_lines(lines, profile)
    stem_indices = [i for i, t in enumerate(tagged) if t.kind is LineKind.STEM_CANDIDATE]
    stem_indices = _filter_increasing_stems(tagged, stem_indices, profile)
    if not stem_indices:
        return []

    page_w = lines[0].page_width
    page_h = lines[0].page_height
    regions: list[McqRegion] = []
    prev_close = 0
    for s_i, stem_at in enumerate(stem_indices):
        end_exclusive = stem_indices[s_i + 1] if s_i + 1 < len(stem_indices) else len(tagged)
        close_at = _close_index(tagged, stem_at, end_exclusive)
        member_start = _preamble_start(tagged, stem_at, prev_close, profile)
        region = _build_region(
            tagged,
            stem_at=stem_at,
            member_start=member_start,
            close_at=close_at,
            profile=profile,
            page_w=page_w,
            page_h=page_h,
        )
        if region is not None:
            regions.append(region)
        prev_close = close_at

    if profile.drop_incomplete:
        regions = [
            region
            for i, region in enumerate(regions)
            if not region.incomplete
            or (
                i + 1 < len(regions)
                and regions[i + 1].question_id == region.question_id + 1
            )
        ]

    regions = _recover_orphan_options(
        tagged, regions, profile=profile, page_w=page_w, page_h=page_h
    )
    return _snap_vertical_gaps(
        regions,
        pad=profile.pad_px,
        page_h=page_h,
        footer_margin_px=profile.footer_margin_px,
    )


def _snap_vertical_gaps(
    regions: list[McqRegion],
    *,
    pad: float,
    page_h: float | None = None,
    footer_margin_px: float = 160.0,
) -> list[McqRegion]:
    """Assign vertical gaps between raw text boxes without overlap.

    Default: gap belongs to the previous question (figures below options).
    If the next region is an orphan (OCR missed the stem): gap belongs to next
    (figure above the recovered A-D block).
    Last region on a page extends toward the footer so page-final diagrams are kept.
    """
    if not regions:
        return []
    ordered = sorted(
        regions,
        key=lambda r: (min(r.line_indices) if r.line_indices else 10**9, r.bbox[1]),
    )
    raw = [r.bbox for r in ordered]
    y_bounds: list[list[float]] = [[b[1], b[3]] for b in raw]

    for i in range(len(ordered) - 1):
        prev_y2_raw = raw[i][3]
        next_y1_raw = raw[i + 1][1]
        if (
            ordered[i].incomplete
            and ordered[i + 1].question_id == ordered[i].question_id + 1
        ):
            # A graph-choice question retained by sequence evidence may have no
            # D anchor.  Its raw span reaches the next opener; cut there so the
            # next question's stem/options are not clipped.
            y_bounds[i][1] = min(y_bounds[i][1], next_y1_raw - pad)
            y_bounds[i + 1][0] = next_y1_raw
        elif ordered[i + 1].orphan:
            y_bounds[i + 1][0] = min(y_bounds[i + 1][0], prev_y2_raw)
            y_bounds[i][1] = min(y_bounds[i][1], y_bounds[i + 1][0] - pad)
        else:
            y_bounds[i][1] = max(y_bounds[i][1], next_y1_raw - pad)
            y_bounds[i + 1][0] = max(y_bounds[i + 1][0], y_bounds[i][1] + pad)

    if page_h is not None and ordered:
        floor = max(0.0, page_h - footer_margin_px)
        y_bounds[-1][1] = max(y_bounds[-1][1], floor)

    out: list[McqRegion] = []
    for i, r in enumerate(ordered):
        x1, _, x2, _ = raw[i]
        y1, y2 = y_bounds[i]
        if i > 0 and y1 < out[i - 1].bbox[3] + pad:
            y1 = out[i - 1].bbox[3] + pad
        if page_h is not None:
            y2 = min(y2, page_h)
        if y2 <= y1:
            y2 = y1 + 1.0
        out.append(
            McqRegion(
                question_id=r.question_id,
                bbox=(x1, y1, x2, y2),
                anchors=r.anchors,
                incomplete=r.incomplete,
                line_indices=list(r.line_indices),
                orphan=r.orphan,
            )
        )
    return out
