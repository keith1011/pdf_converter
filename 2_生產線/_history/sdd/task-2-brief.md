### Task 2: Figure caption prompt + `figure_export` helper

**Files:**
- Modify: `src/ocr_pipeline/prompts.py`
- Create: `src/ocr_pipeline/figure_export.py`
- Test: `tests/test_figure_export.py`

**Interfaces:**
- Consumes: `LayoutBlock`, `BlockType.FIGURE`, `VlmClient.generate(prompt, image_path=, max_new_tokens=)`, `FIGURE_CAPTION_PROMPT`
- Produces:
  - `FIGURE_CAPTION_PROMPT: str`
  - `def export_figures(*, blocks: list[LayoutBlock], figures_dir: Path, vlm, max_new_tokens: int = 128) -> tuple[list[ContentSegment], list[str]]`
  - Writes `figures_dir / f"{block.block_id}.png"`; returns segments with `crop_relpath=f"figures/{block.block_id}.png"`; warnings on per-figure failure

- [ ] **Step 1: Write the failing test**

```python
# tests/test_figure_export.py
from __future__ import annotations

from pathlib import Path

from PIL import Image

from ocr_pipeline.figure_export import export_figures
from ocr_pipeline.models import BBox, BlockType, LayoutBlock, SegmentKind


class FakeVlm:
    def generate(self, prompt, image_path=None, max_new_tokens=None):
        assert image_path is not None
        assert "圖" in prompt or "caption" in prompt.lower() or "說明" in prompt
        return "圓形面積示意圖"


def test_export_figures_writes_png_and_segment(tmp_path: Path):
    page = tmp_path / "page.png"
    Image.new("RGB", (40, 40), color=(200, 200, 200)).save(page)
    block = LayoutBlock(
        "p001_b012",
        BlockType.FIGURE,
        BBox(2, 2, 20, 20),
        0,
        1,
        page,
        crop_path=None,
    )
    figures_dir = tmp_path / "figures"
    segs, warns = export_figures(blocks=[block], figures_dir=figures_dir, vlm=FakeVlm())
    assert warns == []
    assert len(segs) == 1
    assert segs[0].kind is SegmentKind.FIGURE
    assert segs[0].text == "圓形面積示意圖"
    assert segs[0].crop_relpath == "figures/p001_b012.png"
    assert (figures_dir / "p001_b012.png").is_file()


class BoomVlm:
    def generate(self, prompt, image_path=None, max_new_tokens=None):
        raise RuntimeError("cuda boom")


def test_export_figures_skips_failed_caption(tmp_path: Path):
    page = tmp_path / "page.png"
    Image.new("RGB", (40, 40), color=(200, 200, 200)).save(page)
    block = LayoutBlock(
        "p001_b099",
        BlockType.FIGURE,
        BBox(2, 2, 20, 20),
        0,
        1,
        page,
    )
    segs, warns = export_figures(
        blocks=[block], figures_dir=tmp_path / "figures", vlm=BoomVlm()
    )
    assert segs == []
    assert any("p001_b099" in w for w in warns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_figure_export.py -q`

Expected: FAIL (`figure_export` missing)

- [ ] **Step 3: Minimal implementation**

Add to `prompts.py`:

```python
FIGURE_CAPTION_PROMPT = """你正在看一張試卷／講義中的圖（圖表、幾何圖、示意圖）。

任務：用一句繁體中文短說明這張圖畫什麼（供題庫檢索）。
規則：
- 只輸出一句話，不要編號、不要 markdown、不要「這張圖是」。
- 不要發明圖中沒有的細節；看不清就寫「圖示（細節不清）」。
"""
```

Create `figure_export.py`:

```python
from __future__ import annotations

from pathlib import Path

from .models import (
    BBox,
    BlockType,
    ContentSegment,
    IntegrityStatus,
    LayoutBlock,
    SegmentKind,
)
from .prompts import FIGURE_CAPTION_PROMPT


def _ensure_crop(block: LayoutBlock, figures_dir: Path) -> Path:
    figures_dir.mkdir(parents=True, exist_ok=True)
    dest = figures_dir / f"{block.block_id}.png"
    if block.crop_path is not None and block.crop_path.is_file():
        dest.write_bytes(block.crop_path.read_bytes())
        return dest
    from PIL import Image

    with Image.open(block.image_path) as im:
        image = im.convert("RGB")
        image.load()
        w, h = image.size
        box = block.bbox.clamp(w, h).as_int_tuple()
        crop = image.crop(box)
    crop.save(dest)
    return dest


def export_figures(
    *,
    blocks: list[LayoutBlock],
    figures_dir: Path,
    vlm,
    max_new_tokens: int = 128,
) -> tuple[list[ContentSegment], list[str]]:
    segments: list[ContentSegment] = []
    warnings: list[str] = []
    for block in blocks:
        if block.block_type is not BlockType.FIGURE:
            continue
        try:
            crop_path = _ensure_crop(block, figures_dir)
            caption = vlm.generate(
                FIGURE_CAPTION_PROMPT,
                image_path=crop_path,
                max_new_tokens=max_new_tokens,
            ).strip()
            if not caption:
                raise RuntimeError("empty caption")
            segments.append(
                ContentSegment(
                    kind=SegmentKind.FIGURE,
                    text=caption,
                    source_block_id=block.block_id,
                    bbox=block.bbox,
                    integrity=IntegrityStatus.OK,
                    crop_relpath=f"figures/{block.block_id}.png",
                )
            )
        except Exception as exc:  # noqa: BLE001 — per-figure isolation
            warnings.append(f"figure {block.block_id}: {exc}")
    return segments, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_figure_export.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add src/ocr_pipeline/prompts.py src/ocr_pipeline/figure_export.py tests/test_figure_export.py
git commit -m "feat: export figure crops and Qwen captions"
```

---
