from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ocr_pipeline.factory import build_vlm_client, load_ocr_config

from .classification_models import ClassifiedFigureAsset, ReviewedClassification
from .classification_prompt import FIGURE_CLASSIFICATION_PROMPT_VERSION
from .classification_review import review_bundle
from .classification_runner import classify_bundle

VISUAL_FAMILIES = (
    "geometry",
    "coordinate_graph",
    "function_graph",
    "statistical_chart",
    "table",
    "physical_diagram",
    "illustration",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Figure Phase B2 Qwen semantic classification"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    propose = commands.add_parser("propose", help="create a pending B2 proposal")
    propose.add_argument("--asset", type=Path, required=True)
    propose.add_argument("--out", type=Path, required=True)
    propose.add_argument("--config", type=Path)

    review = commands.add_parser("review", help="publish an explicit human review")
    review.add_argument("--asset", type=Path, required=True)
    review.add_argument("--out", type=Path, required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument(
        "--status",
        choices=("approved", "corrected", "rejected"),
        required=True,
    )
    review.add_argument("--visual-family", choices=VISUAL_FAMILIES)
    review.add_argument("--subtype")
    review.add_argument(
        "--secondary-tag",
        action="append",
        choices=VISUAL_FAMILIES,
        default=[],
    )
    return parser


def _usage_error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def _source_proposal_id(asset_dir: Path) -> str:
    asset = ClassifiedFigureAsset.model_validate_json(
        (asset_dir / "figure_asset.json").read_text(encoding="utf-8")
    )
    proposal = asset.classification.proposed
    if proposal is None:
        _usage_error("review requires a pending B2 proposal")
    return f"{asset.asset_id}:{proposal.prompt_version}"


def _run_propose(args: argparse.Namespace) -> int:
    config = load_ocr_config(args.config)
    classification_config = config.get("figure_classification") or {}
    max_new_tokens = int(classification_config.get("max_new_tokens", 256))
    prompt_version = str(
        classification_config.get(
            "prompt_version",
            FIGURE_CLASSIFICATION_PROMPT_VERSION,
        )
    )
    client = build_vlm_client(config)
    try:
        classify_bundle(
            args.asset,
            args.out,
            client=client,
            max_new_tokens=max_new_tokens,
            prompt_version=prompt_version,
        )
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return 0


def _run_review(args: argparse.Namespace) -> int:
    secondary_tags = list(args.secondary_tag or [])
    if args.status == "rejected":
        if args.visual_family is not None or args.subtype is not None or secondary_tags:
            _usage_error(
                "rejected review cannot use --visual-family, --subtype or "
                "--secondary-tag"
            )
        visual_family = "unknown"
        subtype = "unclassified"
        secondary_tags = []
    else:
        if args.visual_family is None:
            _usage_error(f"{args.status} review requires --visual-family")
        if args.subtype is None:
            _usage_error(f"{args.status} review requires --subtype")
        visual_family = args.visual_family
        subtype = args.subtype

    decision = ReviewedClassification(
        visual_family=visual_family,
        subtype=subtype,
        secondary_tags=secondary_tags,
        status=args.status,
        reviewer=args.reviewer,
        source_proposal_id=_source_proposal_id(args.asset),
    )
    review_bundle(args.asset, args.out, decision)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "propose":
        return _run_propose(args)
    return _run_review(args)
