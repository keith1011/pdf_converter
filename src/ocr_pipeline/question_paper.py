"""Question-paper mode: content crop + single VLM call per page (no block routing)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .assemble import FinalPolisher
from .cli_report import WarnCollector
from .content_crop import CropMargins, crop_page_images
from .engines.timing import StageTimer
from .latex_math import sanitize_tex_document, strip_model_junk
from .models import (
    BBox,
    ContentSegment,
    IntegrityStatus,
    PageIR,
    PageResult,
    PipelineResult,
    SegmentKind,
)
from .prompts import QUESTION_PAPER_PROMPT


def split_question_segments(text: str, page_index: int) -> list[ContentSegment]:
    """Split extracted page text into header + numbered question segments."""
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"(?m)(?=^\d+\.)", text)
    segments: list[ContentSegment] = []
    bbox = BBox(0, 0, 1000, 1000)
    for i, part in enumerate(parts):
        body = part.strip()
        if not body:
            continue
        segments.append(
            ContentSegment(
                kind=SegmentKind.PROSE,
                text=body,
                source_block_id=f"p{page_index}_q{i}",
                bbox=bbox,
                integrity=IntegrityStatus.OK,
            )
        )
    return segments


def write_question_artifacts(
    *,
    source: str,
    output_dir: Path,
    page_texts: list[tuple[int, str]],
    wrap_tex_fn,
) -> tuple[str, str, Path, Path, Path]:
    """Write txt / tex / pageir for question_paper mode."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_ir: list[PageIR] = []
    txt_parts: list[str] = []
    for page_index, text in page_texts:
        cleaned = strip_model_junk(text).strip()
        txt_parts.append(cleaned)
        pages_ir.append(
            PageIR(page_index=page_index, segments=split_question_segments(cleaned, page_index))
        )

    full_txt = "\n\n".join(p for p in txt_parts if p)
    full_tex = sanitize_tex_document(wrap_tex_fn(full_txt))

    txt_path = output_dir / f"{source}.txt"
    tex_path = output_dir / f"{source}.tex"
    pageir_path = output_dir / f"{source}.pageir.json"
    txt_path.write_text(full_txt, encoding="utf-8")
    tex_path.write_text(full_tex, encoding="utf-8")
    from .content_first import _segment_to_dict

    payload = {
        "doc_type": "question_paper",
        "pages": [
            {
                "page_index": p.page_index,
                "segments": [_segment_to_dict(s) for s in p.segments],
            }
            for p in pages_ir
        ],
    }
    pageir_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return full_txt, full_tex, txt_path, tex_path, pageir_path


def run_question_paper(
    *,
    layout,
    vlm,
    pdf_path: Path,
    page_dir: Path,
    output_dir: Path,
    artifact_source: str,
    limit: int = 0,
    overwrite: bool = True,
    margins: CropMargins | None = None,
    max_new_tokens: int = 1024,
    warns: WarnCollector | None = None,
) -> PipelineResult:
    """
    Render → content crop → one VLM extract per page → txt/tex/pageir.

    Does not load Surya / block routers.
    """
    warns = warns or WarnCollector()
    timer = StageTimer()
    polisher = FinalPolisher(vlm)

    with timer.section("layout"):
        print("=== Stage1: PDF -> images (question_paper) ===")
        if page_dir.exists() and any(page_dir.glob("page_*.png")) and not overwrite:
            images = sorted(page_dir.glob("page_*.png"))
            # Prefer full page renders, not prior content crops
            images = [p for p in images if ".content." not in p.name]
            print(f"Reusing images: {page_dir} ({len(images)})")
        else:
            images = layout.pdf_to_images(pdf_path, page_dir, limit=limit)
        if limit > 0:
            images = images[:limit]

    with timer.section("crop"):
        print("=== Content ROI crop ===")
        content_images = crop_page_images(images, margins=margins)
        for src, dest in zip(images, content_images, strict=True):
            print(f"  crop {src.name} -> {dest.name}")

    page_texts: list[tuple[int, str]] = []
    pages: list[PageResult] = []
    with timer.section("extract"):
        print("=== Question extract (VLM, no block route) ===")
        for image_path, content_path in zip(images, content_images, strict=True):
            m = re.search(r"(\d+)", image_path.stem)
            page = int(m.group(1)) if m else len(pages) + 1
            print(f"  page {page}: {content_path.name}")
            raw = vlm.generate(
                QUESTION_PAPER_PROMPT,
                image_path=content_path,
                max_new_tokens=max_new_tokens,
            )
            text = strip_model_junk(raw).strip()
            if "寫於邊界以外" in text:
                warns.add("question_paper still contains margin warning text")
            page_texts.append((page, text))
            pages.append(
                PageResult(
                    page=page,
                    image_path=content_path,
                    blocks=[],
                    draft=text,
                    txt=text,
                    tex=polisher.wrap_tex(text),
                )
            )

    with timer.section("finalize"):
        full_txt, full_tex, txt_path, tex_path, pageir_path = write_question_artifacts(
            source=artifact_source,
            output_dir=output_dir,
            page_texts=page_texts,
            wrap_tex_fn=polisher.wrap_tex,
        )

    timings = timer.as_dict()
    print("TIMING: " + " ".join(f"{name}={value:.3f}s" for name, value in timings.items()))

    return PipelineResult(
        source=artifact_source,
        pages=pages,
        draft=full_txt,
        txt=full_txt,
        tex=full_tex,
        txt_path=txt_path,
        tex_path=tex_path,
        pageir_path=pageir_path,
        warnings=list(warns.items),
    )
