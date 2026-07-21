"""Pipeline orchestrator: extract (layout+route) then arrange (polish)."""

from __future__ import annotations

import re
from pathlib import Path

from .assemble import DraftAssembler, FinalPolisher
from .cli_report import WarnCollector, print_stage3_start
from .latex_math import sanitize_tex_document
from .layout import LayoutAnalyzer
from .models import PageResult, PipelineResult
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

        if polish_per_page:
            txt_parts: list[str] = []
            body_parts: list[str] = []
            for pr in pages:
                print_stage3_start()
                t, x, pw = self.polisher.polish(pr.draft)
                for w in pw:
                    warns.add(w)
                pr.txt, pr.tex = t, x
                txt_parts.append(t)
                body_parts.append(self.polisher.extract_tex_body(x))
            full_txt = "\n\n".join(txt_parts)
            full_tex = sanitize_tex_document(
                self.polisher._wrap_tex("\n\n".join(body_parts))
            )
            draft = "\n\n".join(p.draft for p in pages)
        else:
            draft = "\n\n".join(p.draft for p in pages if p.draft.strip())
            print_stage3_start()
            full_txt, full_tex, pw = self.polisher.polish(draft)
            for w in pw:
                warns.add(w)

        txt_path.write_text(full_txt, encoding="utf-8")
        tex_path.write_text(full_tex, encoding="utf-8")

        return PipelineResult(
            source=source,
            pages=pages,
            draft=draft,
            txt=full_txt,
            tex=full_tex,
            txt_path=txt_path,
            tex_path=tex_path,
            warnings=list(warns.items),
        )
