# Task 2 review package

 src/ocr_pipeline/prompts.py | 8 ++++++++
 1 file changed, 8 insertions(+)

## Diff
```diff

diff --git a/src/ocr_pipeline/prompts.py b/src/ocr_pipeline/prompts.py
index 4be431f..7ade84e 100644
--- a/src/ocr_pipeline/prompts.py
+++ b/src/ocr_pipeline/prompts.py
@@ -108,3 +108,11 @@ CONTENT_FIRST_POLISH_PROMPT = f"""浣犳槸涓€鍊?LaTeX 鎺掔増灏堝銆傝珛灏囦互涓? 
 # Ship 1: content-first is the active polish header.
 POLISH_PROMPT_HEADER = CONTENT_FIRST_POLISH_PROMPT
+
+FIGURE_CAPTION_PROMPT = """浣犳鍦ㄧ湅涓€寮佃│鍗凤紡璎涚京涓殑鍦栵紙鍦栬〃銆佸咕浣曞湒銆佺ず鎰忓湒锛夈€?+
+浠诲嫏锛氱敤涓€鍙ョ箒楂斾腑鏂囩煭瑾槑閫欏嫉鍦栫暙浠€楹硷紙渚涢搴绱級銆?+瑕忓墖锛?+- 鍙几鍑轰竴鍙ヨ┍锛屼笉瑕佺法铏熴€佷笉瑕?markdown銆佷笉瑕併€岄€欏嫉鍦栨槸銆嶃€?+- 涓嶈鐧兼槑鍦栦腑娌掓湁鐨勭窗绡€锛涚湅涓嶆竻灏卞銆屽湒绀猴紙绱扮瘈涓嶆竻锛夈€嶃€?+"""
from __future__ import annotations

from pathlib import Path

from .models import (
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
        except Exception as exc:  # noqa: BLE001 鈥?per-figure isolation
            warnings.append(f"figure {block.block_id}: {exc}")
    return segments, warnings
```

