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
    """Formula/Equation -> MinerU/UniMERNet when available; else VlmClient. Body display $$."""

    def __init__(self, engine: str = "mineru", glm_fallback=None):
        self.engine = engine
        self.glm_fallback = glm_fallback  # VlmClient (name kept for call-site compat)
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
        self._try_init_mineru()
        # TODO: wire concrete MinerU formula OCR when installed
        if self.glm_fallback is None:
            raise RuntimeError("No formula engine available (MinerU missing and no VLM fallback)")
        raw = self.glm_fallback.generate(MATH_ROUTER_PROMPT, image_path=crop_path)
        return normalize_display_math(raw)

    def process(self, block: LayoutBlock) -> LayoutBlock:
        assert block.crop_path is not None
        block.latex = self.extract_latex(block.crop_path)
        block.raw_text = block.latex
        return block


class TextRouter:
    """Text/Title/List/Table crops -> VlmClient (formulas forced to LaTeX)."""

    def __init__(self, vlm, model_name: str = "VlmClient"):
        self.vlm = vlm
        self.model_name = model_name

    def _prompt_for(self, block_type: BlockType) -> str:
        if block_type == BlockType.TABLE:
            return TABLE_ROUTER_PROMPT
        return TEXT_ROUTER_PROMPT

    def process(self, block: LayoutBlock) -> LayoutBlock:
        assert block.crop_path is not None
        prompt = self._prompt_for(block.block_type)
        block.raw_text = self.vlm.generate(prompt, image_path=block.crop_path).strip()
        return block


class DynamicRouter:
    """Crop page regions and dispatch by Surya label (preserve reading order)."""

    MATH_TYPES = {BlockType.FORMULA, BlockType.EQUATION}
    TEXT_TYPES = {BlockType.TEXT, BlockType.TITLE, BlockType.LIST, BlockType.TABLE}

    def __init__(self, math_router: MathRouter, text_router: TextRouter, crop_dir: Path):
        self.math_router = math_router
        self.text_router = text_router
        self.crop_dir = crop_dir
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
        block.crop_path = self.crop(block)
        print(f"    route {block.block_id} [{block.block_type.value}] order={block.order}")
        if block.block_type in self.MATH_TYPES:
            return self.math_router.process(block)
        if block.block_type in self.TEXT_TYPES:
            return self.text_router.process(block)
        block.raw_text = ""
        block.meta["skipped"] = True
        return block

    def route_page(self, blocks: list[LayoutBlock]) -> list[LayoutBlock]:
        ordered = sorted(blocks, key=lambda b: b.order)
        return [self.route_block(b) for b in ordered]
