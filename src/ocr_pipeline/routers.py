"""Stage 2: crop + dynamic routing (Math / Text / Table / optional Figure)."""

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
    """Formula/Equation -> FormulaEngine, or VLM fallback when no engine is wired."""

    def __init__(
        self,
        *,
        formula_engine=None,
        vlm_fallback=None,
        max_new_tokens: int | None = None,
        # Deprecated alias (call-site compat). Prefer ``vlm_fallback``.
        glm_fallback=None,
    ):
        self.formula_engine = formula_engine
        self.vlm_fallback = vlm_fallback if vlm_fallback is not None else glm_fallback
        self.glm_fallback = self.vlm_fallback  # back-compat attribute
        self.max_new_tokens = max_new_tokens

    def extract_latex(self, crop_path: Path) -> str:
        if self.formula_engine is not None:
            return self.formula_engine.ocr(crop_path)
        if self.vlm_fallback is None:
            raise RuntimeError(
                "No formula engine configured (set engines.formula or pass vlm_fallback)"
            )
        raw = self.vlm_fallback.generate(
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
        engine = self.table_engine if block.block_type == BlockType.TABLE else self.text_engine
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
    """Crop page regions and dispatch by layout block type (preserve reading order)."""

    MATH_TYPES = {BlockType.FORMULA, BlockType.EQUATION}
    TEXT_TYPES = {BlockType.TEXT, BlockType.TITLE, BlockType.LIST, BlockType.TABLE}
    FIGURE_TYPES = {BlockType.FIGURE}

    def __init__(
        self,
        math_router: MathRouter,
        text_router: TextRouter,
        crop_dir: Path,
        *,
        skip_figures: bool = True,
    ):
        self.math_router = math_router
        self.text_router = text_router
        self.crop_dir = crop_dir
        self.skip_figures = skip_figures
        self.crop_dir.mkdir(parents=True, exist_ok=True)

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

    def route_block(self, block: LayoutBlock) -> LayoutBlock:
        if block.block_type in self.FIGURE_TYPES and self.skip_figures:
            block.crop_path = self.crop(block)
            print(
                f"    skip-ocr {block.block_id} [{block.block_type.value}] "
                f"order={block.order} (skip_figures; crop kept)"
            )
            block.raw_text = ""
            block.meta["skipped"] = True
            block.meta["skip_reason"] = "skip_figures"
            return block

        block.crop_path = self.crop(block)
        print(f"    route {block.block_id} [{block.block_type.value}] order={block.order}")
        if block.block_type in self.MATH_TYPES:
            return self.math_router.process(block)
        if block.block_type in self.TEXT_TYPES:
            return self.text_router.process(block)
        if block.block_type in self.FIGURE_TYPES:
            # Provisional: VLM/text OCR until dedicated figure-caption path ships.
            return self.text_router.process(block)
        block.raw_text = ""
        block.meta["skipped"] = True
        return block

    def route_page(self, blocks: list[LayoutBlock]) -> list[LayoutBlock]:
        ordered = sorted(blocks, key=lambda b: b.order)
        return [self.route_block(b) for b in ordered]
