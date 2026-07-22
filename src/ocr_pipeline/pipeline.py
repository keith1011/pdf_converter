"""Pipeline orchestrator: extract (layout+route) then arrange (polish)."""

from __future__ import annotations

import re
from pathlib import Path

from .assemble import DraftAssembler, FinalPolisher
from .cli_report import WarnCollector, print_stage3_start
from .content_first import finalize_content_first
from .latex_math import sanitize_tex_document
from .layout import LayoutAnalyzer
from .models import BBox, PageResult, PipelineResult
from .routers import DynamicRouter

# Auto per-page polish thresholds (12GB VRAM — full-doc Stage3 OOMs on long drafts)
_AUTO_PER_PAGE_MIN_PAGES = 3
_AUTO_PER_PAGE_MIN_CHARS = 12_000


def decide_polish_per_page(
    *,
    page_count: int,
    draft_chars: int,
    requested: bool,
) -> bool:
    """
    Content-first Stage3 always polishes each page independently.

    This guarantees that every PageResult receives the polished txt/tex used
    to build PageIR. The arguments remain for CLI/API compatibility.
    """
    return True


class PipelineManager:
    def __init__(
        self,
        layout: LayoutAnalyzer,
        router: DynamicRouter,
        assembler: DraftAssembler,
        polisher: FinalPolisher,
        output_dir: Path = Path("output"),
        pages_dir: Path = Path("data/pdf_pages"),
    ):
        self.layout = layout
        self.router = router
        self.assembler = assembler
        self.polisher = polisher
        self.output_dir = output_dir
        self.pages_dir = pages_dir

    @staticmethod
    def _safe_stem(path: Path) -> str:
        stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", path.stem, flags=re.UNICODE)
        return stem.strip("_") or "pdf"

    def run(
        self,
        pdf_path: Path,
        *,
        limit: int = 0,
        polish_per_page: bool = False,
        overwrite: bool = True,
        warns: WarnCollector | None = None,
    ) -> PipelineResult:
        """
        Order on 12GB VRAM:
          layout all pages → release Surya → route (VLM) → polish (VLM)
        """
        warns = warns or WarnCollector()
        source = self._safe_stem(pdf_path)
        page_dir = self.pages_dir / source
        print("=== Stage1: PDF -> images ===")
        if page_dir.exists() and any(page_dir.glob("page_*.png")) and not overwrite:
            images = sorted(page_dir.glob("page_*.png"))
            print(f"Reusing images: {page_dir} ({len(images)})")
        else:
            images = self.layout.pdf_to_images(pdf_path, page_dir, limit=limit)
        if limit > 0:
            images = images[:limit]

        # --- Stage1 layout only (hold Surya) ---
        pages: list[PageResult] = []
        for image_path in images:
            m = re.search(r"(\d+)", image_path.stem)
            page = int(m.group(1)) if m else len(pages) + 1
            print(f"\n=== Stage1 layout page {page}: {image_path} ===")
            blocks = self.layout.analyze_page(image_path, page)
            if getattr(self.layout, "_backend", None) == "fullpage":
                warns.add("layout fullpage fallback (not golden)")
            print(f"  blocks={len(blocks)}")
            pages.append(
                PageResult(page=page, image_path=image_path, blocks=blocks, draft="")
            )

        # Free layout VRAM before any VLM load (ACCESS_VIOLATION risk on 12GB otherwise)
        self.layout.release()

        # --- Stage2 route (VLM) ---
        for pr in pages:
            print(f"=== Stage2 route page {pr.page} ===")
            pr.blocks = self.router.route_page(pr.blocks)
            pr.draft = self.assembler.stitch(pr.blocks)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        txt_path = self.output_dir / f"{source}.txt"
        tex_path = self.output_dir / f"{source}.tex"

        combined_draft = "\n\n".join(p.draft for p in pages if p.draft.strip())
        if (
            not polish_per_page
            and (
                len(pages) >= _AUTO_PER_PAGE_MIN_PAGES
                or len(combined_draft) >= _AUTO_PER_PAGE_MIN_CHARS
            )
        ):
            warns.add(
                f"auto polish_per_page (pages={len(pages)}, draft_chars={len(combined_draft)})"
            )
            print(
                f"WARN: auto polish_per_page "
                f"(pages={len(pages)}, draft_chars={len(combined_draft)})"
            )

        txt_parts: list[str] = []
        body_parts: list[str] = []
        print_stage3_start()  # DR2: once, then quiet across pages
        for pr in pages:
            t, x, pw = self.polisher.polish(pr.draft)
            for w in pw:
                warns.add(w)
            pr.txt, pr.tex = t, x
            txt_parts.append(t)
            body_parts.append(self.polisher.extract_tex_body(x))
        full_txt = "\n\n".join(txt_parts)
        full_tex = sanitize_tex_document(
            self.polisher.wrap_tex("\n\n".join(body_parts))
        )
        draft = "\n\n".join(p.draft for p in pages)

        # Content-first Ship 1: segment → integrity → render → pageir.json
        # Prefer polished tex body per page; txt/draft are defensive fallbacks.
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

        full_txt, full_tex, txt_path, tex_path, pageir_path, cf_warns = finalize_content_first(
            source=source,
            output_dir=self.output_dir,
            page_drafts=page_drafts,
            wrap_tex_fn=_wrap,
        )
        for w in cf_warns:
            warns.add(w)

        return PipelineResult(
            source=source,
            pages=pages,
            draft=draft,
            txt=full_txt,
            tex=full_tex,
            txt_path=txt_path,
            tex_path=tex_path,
            pageir_path=pageir_path,
            warnings=list(warns.items),
        )
