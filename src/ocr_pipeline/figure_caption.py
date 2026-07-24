"""Figure crop caption via trunk VLM (Traditional Chinese, short)."""

from __future__ import annotations

from pathlib import Path

FIGURE_CAPTION_PROMPT = """你正在看一張試卷／評分參考中的「圖／圖表／示意圖」裁切圖。

任務：用一句繁體中文短說明描述圖的內容（例如直方圖、圓形圖、幾何圖、座標圖）。
規則：
- 只輸出說明文字，不要 markdown、不要編號、不要「圖：」前綴
- 不超過 40 個中文字
- 若無法辨識，輸出：無法辨識的圖
"""


def caption_figure(
    vlm,
    crop_path: Path,
    *,
    max_new_tokens: int = 128,
) -> str | None:
    """
    Return a short caption, or None on failure / empty.

    Caller should warn and skip the figure segment when None.
    """
    if vlm is None:
        return None
    try:
        raw = vlm.generate(
            FIGURE_CAPTION_PROMPT,
            image_path=Path(crop_path),
            max_new_tokens=max_new_tokens,
        )
    except Exception as e:  # noqa: BLE001 — caption is best-effort
        print(f"[figure] caption failed for {crop_path.name}: {e}")
        return None
    text = (raw or "").strip()
    # Drop accidental prefixes
    for prefix in ("圖：", "圖:", "說明：", "說明:"):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
    if not text:
        return None
    # Soft length clamp for ingest
    if len(text) > 80:
        text = text[:80].rstrip()
    return text
