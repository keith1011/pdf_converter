"""Pipeline orchestrator: extract (layout+route) then arrange (polish)."""

from __future__ import annotations

import re
from contextlib import nullcontext
from pathlib import Path

from .assemble import DraftAssembler, FinalPolisher, split_question_chunks
from .cli_report import WarnCollector, print_stage3_start
from .content_first import finalize_content_first
from .engines.timing import StageTimer
from .latex_math import sanitize_tex_document
from .layout import LayoutAnalyzer
from .layout_artifact import (
    layout_artifact_path,
    load_layout_artifact,
    save_layout_artifact,
)
from .models import BBox, BlockType, ContentSegment, PageResult, PipelineResult
from .nup_router import analyze_page_with_nup
from .pipeline_lock import DEFAULT_LOCK_NAME, PipelineLock
from .pylatex_assist import encode_unicode_outside_math
from .routers import DynamicRouter

_QID_LINE = re.compile(r"^(\d{1,2})[\.．]\s*")


def _write_questions_jsonl(path: Path, pages: list[PageResult]) -> int:
    """One JSON object per MCQ (question_id); blank-line boundaries already in .tex/.txt."""
    import json

    rows: list[dict] = []
    for pr in pages:
        polished = {
            int(m.group(1)): chunk
            for chunk in split_question_chunks(pr.txt or pr.draft or "")
            if (m := _QID_LINE.match(chunk.strip()))
        }
        for b in sorted(pr.blocks, key=lambda x: (x.page, x.order)):
            qid = b.meta.get("question_id")
            if not isinstance(qid, int):
                continue
            text = polished.get(qid) or (b.raw_text or "").strip()
            rows.append(
                {
                    "question_id": qid,
                    "page": pr.page,
                    "block_id": b.block_id,
                    "crop_path": str(b.crop_path) if b.crop_path else None,
                    "text": text,
                    "structured_ocr": b.meta.get("structured_ocr"),
                    "structured_ocr_source": b.meta.get("structured_ocr_source"),
                }
            )
    rows.sort(key=lambda r: r["question_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def check_mcq_coverage(pages: list[PageResult]) -> dict[str, object]:
    """Report mandatory DSE Paper 2 Q1--Q45 coverage without blocking draft runs."""
    qids = [
        int(qid)
        for page in pages
        for block in page.blocks
        if isinstance((qid := block.meta.get("question_id")), int)
    ]
    seen = set(qids)
    return {
        "complete": seen == set(range(1, 46)) and len(qids) == 45,
        "qids": sorted(seen),
        "missing_qids": [qid for qid in range(1, 46) if qid not in seen],
        "duplicate_qids": sorted({qid for qid in qids if qids.count(qid) > 1}),
    }



class PipelineManager:
    def __init__(
        self,
        layout: LayoutAnalyzer,
        router: DynamicRouter,
        assembler: DraftAssembler,
        polisher: FinalPolisher,
        output_dir: Path = Path("output"),
        pages_dir: Path = Path("1_收集資料/data/pdf_pages"),
        *,
        layout_engine=None,
        extract_figures: bool = True,
        nup_enabled: bool = False,
        nup_confidence_threshold: float = 0.75,
        nup_margin_norm: float = 0.01,
    ):
        self.layout = layout
        self.layout_engine = layout_engine
        self.router = router
        self.assembler = assembler
        self.polisher = polisher
        self.output_dir = output_dir
        self.pages_dir = pages_dir
        self.extract_figures = extract_figures
        self.nup_enabled = nup_enabled
        self.nup_confidence_threshold = nup_confidence_threshold
        self.nup_margin_norm = nup_margin_norm

    @staticmethod
    def _safe_stem(path: Path) -> str:
        stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", path.stem, flags=re.UNICODE)
        return stem.strip("_") or "pdf"

    def run(
        self,
        pdf_path: Path,
        *,
        limit: int = 0,
        overwrite: bool = True,
        reuse_layout: bool = False,
        single_instance_lock: bool = True,
        skip_polish: bool = False,
        output_tag: str = "",
        warns: WarnCollector | None = None,
    ) -> PipelineResult:
        """
        Order on 12GB VRAM:
          layout all pages → release Surya → route (VLM) → polish (VLM)

        When ``reuse_layout`` is True, load ``1_收集資料/data/pdf_pages/<stem>/layout.json``
        and skip Surya (still needs page PNGs).
        """
        warns = warns or WarnCollector()
        source = self._safe_stem(pdf_path)
        artifact_source = f"{source}.{output_tag}" if output_tag else source
        page_dir = self.pages_dir / source
        lock_cm = (
            PipelineLock(self.output_dir / DEFAULT_LOCK_NAME)
            if single_instance_lock
            else nullcontext()
        )
        with lock_cm:
            return self._run_unlocked(
                pdf_path,
                source=source,
                artifact_source=artifact_source,
                page_dir=page_dir,
                limit=limit,
                overwrite=overwrite,
                reuse_layout=reuse_layout,
                skip_polish=skip_polish,
                warns=warns,
            )

    def _run_unlocked(
        self,
        pdf_path: Path,
        *,
        source: str,
        artifact_source: str,
        page_dir: Path,
        limit: int,
        overwrite: bool,
        reuse_layout: bool,
        skip_polish: bool,
        warns: WarnCollector,
    ) -> PipelineResult:
        timer = StageTimer()
        with timer.section("layout"):
            print("=== Stage1: PDF -> images ===")
            if page_dir.exists() and any(page_dir.glob("page_*.png")) and not overwrite:
                images = sorted(page_dir.glob("page_*.png"))
                print(f"Reusing images: {page_dir} ({len(images)})")
            else:
                images = self.layout.pdf_to_images(pdf_path, page_dir, limit=limit)
            if limit > 0:
                images = images[:limit]

            artifact = layout_artifact_path(page_dir)
            pages: list[PageResult] = []

            if reuse_layout:
                if not artifact.exists():
                    raise FileNotFoundError(
                        f"--reuse-layout requires {artifact}. Run once without the flag first."
                    )
                print(f"=== Stage1 layout: reusing {artifact} ===")
                pages = load_layout_artifact(artifact)
                if limit > 0:
                    pages = pages[:limit]
                # Remap image paths to current page_dir if PNGs were moved
                by_stem = {p.name: p for p in images}
                for pr in pages:
                    name = Path(pr.image_path).name
                    if name in by_stem:
                        pr.image_path = by_stem[name]
                        for b in pr.blocks:
                            b.image_path = pr.image_path
            else:
                # --- Stage1 layout only (hold Surya) ---
                for image_path in images:
                    m = re.search(r"(\d+)", image_path.stem)
                    page = int(m.group(1)) if m else len(pages) + 1
                    print(f"\n=== Stage1 layout page {page}: {image_path} ===")
                    blocks = analyze_page_with_nup(
                        self._analyze,
                        image_path,
                        page=page,
                        page_dir=page_dir,
                        enabled=self.nup_enabled,
                        threshold=self.nup_confidence_threshold,
                        margin_norm=self.nup_margin_norm,
                    )
                    if getattr(self.layout, "_backend", None) == "fullpage":
                        warns.add("layout fullpage fallback (not golden)")
                    print(f"  blocks={len(blocks)}")
                    pages.append(
                        PageResult(page=page, image_path=image_path, blocks=blocks, draft="")
                    )

                save_layout_artifact(
                    artifact, source=source, pdf_path=pdf_path, pages=pages
                )
                print(f"[Layout] Wrote artifact: {artifact}")

            # Free layout VRAM before any VLM load (ACCESS_VIOLATION risk on 12GB otherwise)
            self._release_layout()

        # --- Stage2 route (VLM) ---
        with timer.section("route"):
            for pr in pages:
                print(f"=== Stage2 route page {pr.page} ===")
                pr.blocks = self.router.route_page(pr.blocks)
                pr.draft = self.assembler.stitch(pr.blocks)

        if release_router := getattr(self.router, "release", None):
            release_router()

        self.output_dir.mkdir(parents=True, exist_ok=True)

        with timer.section("skip_polish" if skip_polish else "polish"):
            if skip_polish:
                for pr in pages:
                    body = encode_unicode_outside_math(pr.draft or "")
                    pr.txt = body
                    pr.tex = sanitize_tex_document(self.polisher.wrap_tex(body))
            else:
                # Content-first: polish each page. MCQ keeps Stage2 crop text
                # (sanitize) unless mcq_stage3=vlm.
                print_stage3_start()  # DR2: once, then quiet across pages
                for pr in pages:
                    if not (pr.draft or "").strip():
                        # Cover / empty layout pages: do not call VLM polish
                        # (empty prompt → model echoes LATEX_MATH_RULES into body).
                        pr.txt, pr.tex = "", sanitize_tex_document(
                            self.polisher.wrap_tex("")
                        )
                        continue
                    is_mcq = any(
                        isinstance(b.meta.get("question_id"), int) for b in pr.blocks
                    )
                    if is_mcq:
                        t, x, pw = self.polisher.polish_mcq(pr.draft)
                    else:
                        t, x, pw = self.polisher.polish(pr.draft)
                    for w in pw:
                        warns.add(w)
                    pr.txt, pr.tex = t, x
        draft = "\n\n".join(p.draft for p in pages)

        figure_segments_by_page: dict[int, list[ContentSegment]] = {}
        figure_blocks = [
            block
            for page in pages
            for block in page.blocks
            if block.block_type is BlockType.FIGURE
        ]
        if self.extract_figures and figure_blocks:
            from .figure_export import export_figures

            with timer.section("figure_export"):
                segments, figure_warns = export_figures(
                    blocks=figure_blocks,
                    figures_dir=self.output_dir / artifact_source / "figures",
                    vlm=self.polisher.vlm,
                )
            for warning in figure_warns:
                warns.add(warning)
            page_by_block_id = {block.block_id: block.page for block in figure_blocks}
            for segment in segments:
                page_index = page_by_block_id.get(segment.source_block_id)
                if page_index is None:
                    page_index = int(segment.source_block_id.split("_", 1)[0][1:])
                figure_segments_by_page.setdefault(page_index, []).append(segment)

        page_drafts: list[tuple[int, str, BBox]] = []
        for pr in pages:
            if pr.tex:
                text_for_seg = self.polisher.extract_tex_body(pr.tex)
            elif pr.txt:
                text_for_seg = pr.txt
            else:
                text_for_seg = pr.draft
            page_drafts.append((pr.page, text_for_seg, BBox(0, 0, 1000, 1000)))

        def _wrap(body: str) -> str:
            return sanitize_tex_document(self.polisher.wrap_tex(body))

        with timer.section("finalize"):
            full_txt, full_tex, txt_path, tex_path, pageir_path, cf_warns = (
                finalize_content_first(
                    source=artifact_source,
                    output_dir=self.output_dir,
                    page_drafts=page_drafts,
                    wrap_tex_fn=_wrap,
                    figure_segments_by_page=figure_segments_by_page,
                )
            )
        for w in cf_warns:
            warns.add(w)

        n_q = sum(
            1
            for pr in pages
            for b in pr.blocks
            if isinstance(b.meta.get("question_id"), int)
        )
        questions_path = None
        if n_q:
            questions_path = self.output_dir / f"{artifact_source}.questions.jsonl"
            written = _write_questions_jsonl(questions_path, pages)
            print(f"[MCQ] Wrote {questions_path.name} ({written} questions)", flush=True)
            coverage = check_mcq_coverage(pages)
            if not coverage["complete"]:
                warns.add(
                    "mcq coverage incomplete: "
                    f"missing={coverage['missing_qids']} "
                    f"duplicates={coverage['duplicate_qids']}"
                )

        timings = timer.as_dict()
        print("TIMING: " + " ".join(f"{name}={value:.3f}s" for name, value in timings.items()))

        return PipelineResult(
            source=artifact_source,
            pages=pages,
            draft=draft,
            txt=full_txt,
            tex=full_tex,
            txt_path=txt_path,
            tex_path=tex_path,
            pageir_path=pageir_path,
            warnings=list(warns.items),
        )

    def _analyze(self, image_path: Path, page: int):
        if self.layout_engine is not None:
            return self.layout_engine.analyze(image_path, page)
        return self.layout.analyze_page(image_path, page)

    def _release_layout(self) -> None:
        engine = self.layout_engine or self.layout
        engine.release()
