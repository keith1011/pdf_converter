"""Subject profiles for DSE MCQ region detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MATH_CP_P2 = _REPO_ROOT / "2_生產線" / "config" / "profiles" / "math_cp_p2.yaml"


@dataclass(frozen=True)
class McqProfile:
    id: str
    dual_column: bool
    stem_opener_patterns: tuple[re.Pattern[str], ...]
    option_letters: tuple[str, ...]
    option_patterns: tuple[re.Pattern[str], ...]
    left_bias_ratio: float
    min_option_hits: int
    pad_px: float = 8.0
    question_id_min: int = 1
    question_id_max: int = 45
    require_increasing_ids: bool = True
    drop_incomplete: bool = True
    recover_orphan_options: bool = True
    # Expand crop width toward page edge so diagrams are not clipped
    content_x_max_ratio: float = 0.96
    # Only pull stem-preamble lines within this many px above the opener
    preamble_max_gap_px: float = 120.0
    # Extra room below option D (diagrams often hang slightly past the last option)
    below_options_pad_px: float = 48.0
    # Page-leading orphan: reserve room above the first light-OCR line for qid/formula
    leading_orphan_top_pad_px: float = 64.0
    # Last question on a page: extend y2 up to this margin above page bottom
    footer_margin_px: float = 160.0


def default_math_cp_p2_path() -> Path:
    return _DEFAULT_MATH_CP_P2


def load_mcq_profile(path: Path) -> McqProfile:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"MCQ profile must be a mapping: {path}")

    stem_raw = (data.get("stem_opener") or {}).get("patterns") or []
    opt = data.get("option_anchors") or {}
    letters = tuple(str(x) for x in (opt.get("letters") or ["A", "B", "C", "D"]))
    opt_raw = opt.get("patterns") or []
    margins = data.get("margins") or {}

    return McqProfile(
        id=str(data.get("id") or path.stem),
        dual_column=bool(data.get("dual_column", False)),
        stem_opener_patterns=tuple(re.compile(p) for p in stem_raw),
        option_letters=letters,
        option_patterns=tuple(re.compile(p) for p in opt_raw),
        left_bias_ratio=float(margins.get("left_bias_ratio", 0.25)),
        min_option_hits=int(data.get("min_option_hits", 3)),
        pad_px=float(data.get("pad_px", 8.0)),
        question_id_min=int(data.get("question_id_min", 1)),
        question_id_max=int(data.get("question_id_max", 45)),
        require_increasing_ids=bool(data.get("require_increasing_ids", True)),
        drop_incomplete=bool(data.get("drop_incomplete", True)),
        recover_orphan_options=bool(data.get("recover_orphan_options", True)),
        content_x_max_ratio=float(data.get("content_x_max_ratio", 0.96)),
        preamble_max_gap_px=float(data.get("preamble_max_gap_px", 120.0)),
        below_options_pad_px=float(data.get("below_options_pad_px", 48.0)),
        leading_orphan_top_pad_px=float(
            data.get("leading_orphan_top_pad_px", 64.0)
        ),
        footer_margin_px=float(data.get("footer_margin_px", 160.0)),
    )
