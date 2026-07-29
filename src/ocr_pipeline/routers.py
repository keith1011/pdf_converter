"""Stage 2: crop + dynamic routing (Math / Text / Table / optional Figure)."""

from __future__ import annotations

import re
import time
from pathlib import Path

from .models import BlockType, LayoutBlock
from .prompts import (
    MATH_ROUTER_PROMPT,
    MCQ_ROUTER_PROMPT,
    TABLE_ROUTER_PROMPT,
    TEXT_ROUTER_PROMPT,
)


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
    ):
        self.formula_engine = formula_engine
        self.vlm_fallback = vlm_fallback
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
        structured_ocr_client=None,
        structured_ocr_shadow_mode: bool = True,
    ):
        self.vlm = vlm
        self.model_name = model_name
        self.text_engine = text_engine
        self.table_engine = table_engine
        self.max_new_tokens = max_new_tokens
        self.structured_ocr_client = structured_ocr_client
        self.structured_ocr_shadow_mode = structured_ocr_shadow_mode

    def _prompt_for(self, block: LayoutBlock) -> str:
        if isinstance(block.meta.get("question_id"), int):
            return MCQ_ROUTER_PROMPT
        if block.block_type == BlockType.TABLE:
            return TABLE_ROUTER_PROMPT
        return TEXT_ROUTER_PROMPT

    def process(self, block: LayoutBlock) -> LayoutBlock:
        assert block.crop_path is not None
        prompt = self._prompt_for(block)
        engine = self.table_engine if block.block_type == BlockType.TABLE else self.text_engine
        if engine is not None:
            # Prefer per-block prompt (MCQ vs text) when the engine accepts it.
            try:
                block.raw_text = engine.ocr(block.crop_path, prompt=prompt)
            except TypeError:
                block.raw_text = engine.ocr(block.crop_path)
        else:
            if self.vlm is None:
                raise RuntimeError("No text engine available")
            block.raw_text = self.vlm.generate(
                prompt,
                image_path=block.crop_path,
                max_new_tokens=self.max_new_tokens,
            ).strip()
        self._attach_mcq_structured_ocr(block, prompt)
        return block

    def _attach_mcq_structured_ocr(self, block: LayoutBlock, prompt: str) -> None:
        question_id = block.meta.get("question_id")
        client = self.structured_ocr_client
        if not isinstance(question_id, int) or client is None:
            return

        from .mcq_structured import McqOcrResult, render_text

        try:
            result = McqOcrResult.model_validate(
                client.extract(prompt=prompt, image_path=block.crop_path)
            )
        except Exception as exc:
            block.meta["structured_ocr"] = None
            block.meta["structured_ocr_error"] = type(exc).__name__
            if self.structured_ocr_shadow_mode:
                return
            raise

        block.meta["structured_ocr"] = result.model_dump(mode="json")
        block.meta["structured_ocr_shadow"] = self.structured_ocr_shadow_mode
        if not self.structured_ocr_shadow_mode:
            block.raw_text = render_text(question_id, result)


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
        print(f"    route {block.block_id} [{block.block_type.value}] order={block.order}", flush=True)
        t0 = time.perf_counter()
        try:
            if block.block_type in self.MATH_TYPES:
                out = self.math_router.process(block)
            elif block.block_type in self.TEXT_TYPES:
                out = self.text_router.process(block)
            elif block.block_type in self.FIGURE_TYPES:
                # Provisional: VLM/text OCR until dedicated figure-caption path ships.
                out = self.text_router.process(block)
            else:
                block.raw_text = ""
                block.meta["skipped"] = True
                out = block
        finally:
            dt = time.perf_counter() - t0
            print(f"    done {block.block_id} {dt:.1f}s", flush=True)
        return out

    def route_page(self, blocks: list[LayoutBlock]) -> list[LayoutBlock]:
        ordered = sorted(blocks, key=lambda b: b.order)
        return [self.route_block(b) for b in ordered]
