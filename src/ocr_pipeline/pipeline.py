"""Pipeline orchestrator: extract (layout+route) then arrange (polish)."""

from __future__ import annotations

import re
from contextlib import nullcontext
from pathlib import Path

from .assemble import DraftAssembler, FinalPolisher
from .cli_report import WarnCollector, print_stage3_start
from .content_crop import crop_page_images
from .content_first import finalize_content_first
from .engines.timing import StageTimer
from .latex_math import sanitize_tex_document
from .layout import LayoutAnalyzer
from .layout_artifact import (
    layout_artifact_path,
    load_layout_artifact,
    save_layout_artifact,
)
from .models import BBox, PageResult, PipelineResult
from .pipeline_lock import DEFAULT_LOCK_NAME, PipelineLock
from .question_paper import run_question_paper
from .routers import DynamicRouter


class PipelineManager:
    def __init__(
        self,
        layout: LayoutAnalyzer,
        router: DynamicRouter,
        assembler: DraftAssembler,
        polisher: FinalPolisher,
        output_dir: Path = Path("output"),
        pages_dir: Path = Path("data/pdf_pages"),
        *,
        layout_engine=None,
        vlm=None,
        doc_type: str = "marking_scheme",
        question_margins=None,
        question_max_tokens: int = 1024,
        apply_content_crop: bool = False,
    ):
        self.layout = layout
        self.layout_engine = layout_engine
        self.router = router
        self.assembler = assembler
        self.polisher = polisher
        self.output_dir = output_dir
        self.pages_dir = pages_dir
        self.vlm = vlm
        self.doc_type = (doc_type or "marking_scheme").strip().lower()
        self.question_margins = question_margins
        self.question_max_tokens = question_max_tokens
        self.apply_content_crop = bool(apply_content_crop)

    @staticmethod
    def _safe_stem(path: Path) -> str:
        stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", path.stem, flags=re.UNICODE)
        return stem.strip("_") or "pdf"

    def run(
        self,
        pdf_path: Path,
        *,
        limit: int = 0,
        polish_per_page: bool = False,  # noqa: ARG002 — kept for CLI compat; always per-page
        overwrite: bool = True,
        reuse_layout: bool = False,
        single_instance_lock: bool = True,
        skip_polish: bool = False,
        output_tag: str = "",
        doc_type: str | None = None,
        apply_content_crop: bool | None = None,
        warns: WarnCollector | None = None,
    ) -> PipelineResult:
        """
        Order on 12GB VRAM:
          layout all pages → release Surya → route (VLM) → polish (VLM)

        Content-first always polishes each page (``polish_per_page`` is ignored).

        When ``reuse_layout`` is True, load ``data/pdf_pages/<stem>/layout.json``
        and skip Surya (still needs page PNGs).

        ``doc_type=question_paper`` skips Surya/block routing and extracts stems only.
        ``apply_content_crop`` crops to the DSE content box before layout/routing.
        """
        warns = warns or WarnCollector()
        source = self._safe_stem(pdf_path)
        artifact_source = f"{source}.{output_tag}" if output_tag else source
        page_dir = self.pages_dir / source
        effective_doc_type = (doc_type or self.doc_type or "marking_scheme").strip().lower()
        do_crop = self.apply_content_crop if apply_content_crop is None else bool(apply_content_crop)
        lock_cm = (
            PipelineLock(self.output_dir / DEFAULT_LOCK_NAME)
            if single_instance_lock
            else nullcontext()
        )
        with lock_cm:
            if effective_doc_type == "question_paper":
                if self.vlm is None:
                    raise RuntimeError("question_paper mode requires a VLM client on PipelineManager")
                return run_question_paper(
                    layout=self.layout,
                    vlm=self.vlm,
                    pdf_path=pdf_path,
                    page_dir=page_dir,
                    output_dir=self.output_dir,
                    artifact_source=artifact_source,
                    limit=limit,
                    overwrite=overwrite,
                    margins=self.question_margins,
                    max_new_tokens=self.question_max_tokens,
                    warns=warns,
                )
            return self._run_unlocked(
                pdf_path,
                source=source,
                artifact_source=artifact_source,
                page_dir=page_dir,
                limit=limit,
                overwrite=overwrite,
                reuse_layout=reuse_layout,
                skip_polish=skip_polish,
                apply_content_crop=do_crop,
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
        apply_content_crop: bool,
        warns: WarnCollector,
    ) -> PipelineResult:
        timer = StageTimer()
        with timer.section("layout"):
            print("=== Stage1: PDF -> images ===")
            if page_dir.exists() and any(page_dir.glob("page_*.png")) and not overwrite:
                images = sorted(
                    p for p in page_dir.glob("page_*.png") if ".content." not in p.name
                )
                print(f"Reusing images: {page_dir} ({len(images)})")
            else:
                images = self.layout.pdf_to_images(pdf_path, page_dir, limit=limit)
            if limit > 0:
                images = images[:limit]

            if apply_content_crop:
                print("=== Content ROI crop (before layout) ===")
                images = crop_page_images(images, margins=self.question_margins)
                for p in images:
                    print(f"  using {p.name}")

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
                    m = re.search(r"(\d+)", image_path.stem.replace(".content", ""))
                    page = int(m.group(1)) if m else len(pages) + 1
                    print(f"\n=== Stage1 layout page {page}: {image_path} ===")
                    blocks = self._analyze(image_path, page)
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

        self.output_dir.mkdir(parents=True, exist_ok=True)

        with timer.section("skip_polish" if skip_polish else "polish"):
            if skip_polish:
                for pr in pages:
                    pr.txt = pr.draft
                    pr.tex = sanitize_tex_document(self.polisher.wrap_tex(pr.draft))
            else:
                # Content-first: always polish each page independently for PageIR.
                print_stage3_start()  # DR2: once, then quiet across pages
                for pr in pages:
                    t, x, pw = self.polisher.polish(pr.draft)
                    for w in pw:
                        warns.add(w)
                    pr.txt, pr.tex = t, x
        draft = "\n\n".join(p.draft for p in pages)

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
                )
            )
        for w in cf_warns:
            warns.add(w)

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
