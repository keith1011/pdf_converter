"""Best-effort semantic labels for N-up panels (EN/ZH)."""

from __future__ import annotations

import re

from .nup_types import NupDecision, NupPanel

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")


def guess_semantic(text: str) -> str | None:
    body = (text or "").strip()
    if len(body) < 8:
        return None
    cjk = len(_CJK.findall(body))
    latin = len(_LATIN.findall(body))
    total = cjk + latin
    if total == 0:
        return None
    if cjk / total >= 0.4:
        return "zh"
    if latin / total >= 0.6:
        return "en"
    return None


def maybe_label_panels(
    decision: NupDecision, drafts: dict[str, str]
) -> NupDecision:
    """Attach semantic labels when heuristics are confident; keep vN ids."""
    labeled: list[NupPanel] = []
    for panel in decision.panels:
        semantic = guess_semantic(drafts.get(panel.version_id, ""))
        labeled.append(
            NupPanel(
                version_id=panel.version_id,
                bbox_norm=panel.bbox_norm,
                path=panel.path,
                semantic=semantic if semantic else panel.semantic,
            )
        )
    return NupDecision(
        page_index=decision.page_index,
        nup_class=decision.nup_class,
        confidence=decision.confidence,
        threshold=decision.threshold,
        fallback=decision.fallback,
        panels=labeled,
    )
