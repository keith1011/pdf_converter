"""Stage 2: crop + dynamic routing (Math / Text / Table)."""

from __future__ import annotations

import re
from pathlib import Path

from .models import BlockType, LayoutBlock
from .prompts import MATH_ROUTER_PROMPT, TABLE_ROUTER_PROMPT, TEXT_ROUTER_PROMPT


def normalize_display_math(text: str) -> str:
    """Wrap a standalone Formula/Equation crop as $$...$$ (body display, not table cells)."""

    s = text.strip()
    if not s:
        return s
    s = re.sub(r"^\$\$\s*", "", s)
    s = re.sub(r"\s*\$\$$", "", s)
    s = s.strip().strip("$").strip()
    # drop accidental code fences
    s = re.sub(r"^```(?:latex|tex)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return f"$$\n{s}\n$$"


class MathRouter:
    """Formula/Equation -> FormulaEngine, with legacy VLM fallback support."""

    def __init__(
        self,
        engine: str = "mineru",
        glm_fallback=None,
        *,
        formula_engine=None,
        max_new_tokens: int | None = None,
    ):
        self.engine = engine
        self.glm_fallback = glm_fallback  # VlmClient (name kept for call-site compat)
        self.formula_engine = formula_engine
        self.max_new_tokens = max_new_tokens
        self._ready = False

    def _try_init_mineru(self) -> bool:
        if self._ready:
            return True
        try:
            import importlib

            for name in ("magic_pdf", "mineru", "unimernet"):
                try:
                    importlib.import_module(name)
                    self._ready = True
                    print(f"[MathRouter] Found package: {name}")
                    return True
                except ImportError:
                    continue
        except Exception:
            pass
        print("[MathRouter] MinerU/UniMERNet not found; will use VLM fallback for formulas")
        return False

    def extract_latex(self, crop_path: Path) -> str:
        if self.formula_engine is not None:
            return self.formula_engine.ocr(crop_path)
        self._try_init_mineru()
        # TODO: wire concrete MinerU formula OCR when installed
        if self.glm_fallback is None:
            raise RuntimeError("No formula engine available (MinerU missing and no VLM fallback)")
        raw = self.glm_fallback.generate(
            MATH_ROUTER_PROMPT,
            image_path=crop_path,
            max_new_tokens=self.max_new_tokens,
        )
        return normalize_display_math(raw)

    def process(self, block: LayoutBlock) -> LayoutBlock:
        assert block.crop_path is not None
        block.latex = self.extract_latex(block.crop_path)
        block.raw_text = block.latex
        return block


class TextRouter:
    """Text/Title/List/Table crops -> TextEngine (formulas forced to LaTeX)."""

    def __init__(
        self,
        vlm=None,
        model_name: str = "VlmClient",
        *,
        text_engine=None,
        table_engine=None,
        max_new_tokens: int | None = None,
    ):
        self.vlm = vlm
        self.model_name = model_name
        self.text_engine = text_engine
        self.table_engine = table_engine
        self.max_new_tokens = max_new_tokens

    def _prompt_for(self, block_type: BlockType) -> str:
        if block_type == BlockType.TABLE:
            return TABLE_ROUTER_PROMPT
        return TEXT_ROUTER_PROMPT

    def process(self, block: LayoutBlock) -> LayoutBlock:
        assert block.crop_path is not None
        engine = (
            self.table_engine if block.block_type == BlockType.TABLE else self.text_engine
        )
        if engine is not None:
            block.raw_text = engine.ocr(block.crop_path)
            return block
        if self.vlm is None:
            raise RuntimeError("No text engine available")
        prompt = self._prompt_for(block.block_type)
        block.raw_text = self.vlm.generate(
            prompt,
            image_path=block.crop_path,
            max_new_tokens=self.max_new_tokens,
        ).strip()
        return block


class DynamicRouter:
    """Crop page regions and dispatch by Surya label (preserve reading order)."""

    MATH_TYPES = {BlockType.FORMULA, BlockType.EQUATION}
    TEXT_TYPES = {BlockType.TEXT, BlockType.TITLE, BlockType.LIST, BlockType.TABLE}
    FIGURE_TYPES = {BlockType.FIGURE}

    def __init__(
        self,
        math_router: MathRouter,
        text_router: TextRouter,
        crop_dir: Path,
        *,
        figures_dir: Path | None = None,
        vlm=None,
        skip_figures: bool = True,
        max_new_tokens_figure: int | None = None,
    ):
        self.math_router = math_router
        self.text_router = text_router
        self.crop_dir = crop_dir
        self.crop_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir = figures_dir
        self.vlm = vlm
        self.skip_figures = bool(skip_figures)
        self.max_new_tokens_figure = max_new_tokens_figure

    def crop(self, block: LayoutBlock) -> Path:
        from PIL import Image

        with Image.open(block.image_path) as im:
            image = im.convert("RGB")
            image.load()
            w, h = image.size
            box = block.bbox.clamp(w, h).as_int_tuple()
            # small padding helps OCR edges
            pad = 2
            x1, y1, x2, y2 = box
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(w, x2 + pad)
            y2 = min(h, y2 + pad)
            crop = image.crop((x1, y1, x2, y2))

        out = self.crop_dir / f"{block.block_id}.png"
        crop.save(out)
        return out

    def _process_figure(self, block: LayoutBlock) -> LayoutBlock:
        """Crop + caption; on failure skip this figure only."""
        from .figure_caption import caption_figure

        assert block.crop_path is not None
        if self.skip_figures or self.vlm is None or self.figures_dir is None:
            block.raw_text = ""
            block.meta["skipped"] = True
            return block

        self.figures_dir.mkdir(parents=True, exist_ok=True)
        dest = self.figures_dir / f"{block.block_id}.png"
        try:
            from shutil import copy2

            copy2(block.crop_path, dest)
        except OSError as e:
            print(f"[figure] copy crop failed {block.block_id}: {e}")
            block.raw_text = ""
            block.meta["skipped"] = True
            return block

        caption = caption_figure(
            self.vlm,
            dest,
            max_new_tokens=self.max_new_tokens_figure or 128,
        )
        if not caption:
            print(f"[figure] skip (no caption): {block.block_id}")
            block.raw_text = ""
            block.meta["skipped"] = True
            # Keep crop file for debugging; omit from pageir
            return block

        rel = f"figures/{block.block_id}.png"
        block.raw_text = caption
        block.meta["crop_relpath"] = rel
        block.meta["is_figure"] = True
        return block

    def route_block(self, block: LayoutBlock) -> LayoutBlock:
        block.crop_path = self.crop(block)
        print(f"    route {block.block_id} [{block.block_type.value}] order={block.order}")
        if block.block_type in self.MATH_TYPES:
            return self.math_router.process(block)
        if block.block_type in self.TEXT_TYPES:
            return self.text_router.process(block)
        if block.block_type in self.FIGURE_TYPES:
            return self._process_figure(block)
        block.raw_text = ""
        block.meta["skipped"] = True
        return block

    def route_page(self, blocks: list[LayoutBlock]) -> list[LayoutBlock]:
        ordered = sorted(blocks, key=lambda b: b.order)
        return [self.route_block(b) for b in ordered]
