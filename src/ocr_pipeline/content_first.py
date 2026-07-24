"""Content-first Ship 1: segment → integrity → linear render → pageir.json."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .formula_integrity import check_math_body
from .models import BBox, ContentSegment, PageIR, SegmentKind
from .segmenter import segment_stitched_page


def render_page_ir(page: PageIR) -> tuple[str, str]:
    """Linear txt and tex_body from PageIR segments (no tabular)."""
    lines: list[str] = []
    for seg in page.segments:
        if seg.kind is SegmentKind.PROSE:
            lines.append(seg.text)
        elif seg.kind is SegmentKind.MATH:
            body = _math_body_for_render(seg.text)
            if body:
                lines.append(f"${body}$")
        elif seg.kind is SegmentKind.MARK_NOTE:
            lines.append(f"(分註: {seg.text})")
        elif seg.kind is SegmentKind.FIGURE:
            lines.append(f"(圖: {seg.text})")
        else:
            lines.append(seg.text)
    joined = "\n".join(lines)
    return joined, joined


def _math_body_for_render(text: str) -> str:
    """Strip bare $ from math bodies; keep \\$ currency."""
    out: list[str] = []
    i = 0
    body = text.strip()
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body) and body[i + 1] == "$":
            out.append("\\$")
            i += 2
            continue
        if body[i] == "$":
            i += 1
            continue
        out.append(body[i])
        i += 1
    return "".join(out).strip()


def apply_integrity_to_page(page: PageIR) -> tuple[PageIR, list[str]]:
    """Run check_math_body on MATH segments; update text + integrity; collect warnings."""
    warnings: list[str] = []
    new_segments: list[ContentSegment] = []
    for seg in page.segments:
        if seg.kind is SegmentKind.MATH:
            status, repaired, warns = check_math_body(seg.text)
            warnings.extend(warns)
            new_segments.append(
                ContentSegment(
                    kind=seg.kind,
                    text=repaired,
                    source_block_id=seg.source_block_id,
                    bbox=seg.bbox,
                    integrity=status,
                    crop_relpath=seg.crop_relpath,
                )
            )
        else:
            new_segments.append(seg)
    return PageIR(page_index=page.page_index, segments=new_segments), warnings


def write_pageir_json(path: Path, pages: list[PageIR]) -> None:
    """Serialize PageIR list to pageir.json."""
    payload = {
        "pages": [
            {
                "page_index": p.page_index,
                "segments": [
                    {
                        "kind": s.kind.value,
                        "text": s.text,
                        "source_block_id": s.source_block_id,
                        "bbox": [s.bbox.x1, s.bbox.y1, s.bbox.x2, s.bbox.y2],
                        "integrity": s.integrity.value,
                        "crop_relpath": s.crop_relpath,
                    }
                    for s in p.segments
                ],
            }
            for p in pages
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_page_ir_from_stitched(
    page_index: int,
    stitched_text: str,
    page_bbox: BBox,
) -> tuple[PageIR, list[str]]:
    """segment_stitched_page then apply_integrity_to_page."""
    page = segment_stitched_page(
        page_index=page_index,
        stitched_text=stitched_text,
        page_bbox=page_bbox,
    )
    return apply_integrity_to_page(page)


def render_document(pages: list[PageIR]) -> tuple[str, str]:
    """Full document txt and tex_body; pages joined by blank line."""
    txt_parts: list[str] = []
    tex_parts: list[str] = []
    for page in pages:
        t, x = render_page_ir(page)
        if t.strip():
            txt_parts.append(t)
        if x.strip():
            tex_parts.append(x)
    return "\n\n".join(txt_parts), "\n\n".join(tex_parts)


def finalize_content_first(
    *,
    source: str,
    output_dir: Path,
    page_drafts: list[tuple[int, str, BBox]],
    wrap_tex_fn: Callable[[str], str],
    figure_segments_by_page: dict[int, list[ContentSegment]] | None = None,
) -> tuple[str, str, Path, Path, Path, list[str]]:
    """
    Build PageIR per page, render, wrap tex, write txt/tex/pageir.json.

    Returns (full_txt, full_tex, txt_path, tex_path, pageir_path, warnings).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_ir: list[PageIR] = []
    all_warnings: list[str] = []

    for page_index, stitched_text, page_bbox in page_drafts:
        page, warns = build_page_ir_from_stitched(page_index, stitched_text, page_bbox)
        if figure_segments_by_page:
            extra = figure_segments_by_page.get(page_index) or []
            if extra:
                page = PageIR(
                    page_index=page.page_index,
                    segments=[*page.segments, *extra],
                )
        pages_ir.append(page)
        all_warnings.extend(warns)

    full_txt, tex_body = render_document(pages_ir)
    full_tex = wrap_tex_fn(tex_body)

    txt_path = output_dir / f"{source}.txt"
    tex_path = output_dir / f"{source}.tex"
    pageir_path = output_dir / f"{source}.pageir.json"

    txt_path.write_text(full_txt, encoding="utf-8")
    tex_path.write_text(full_tex, encoding="utf-8")
    write_pageir_json(pageir_path, pages_ir)

    return full_txt, full_tex, txt_path, tex_path, pageir_path, all_warnings
