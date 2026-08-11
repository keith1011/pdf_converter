from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from ocr_pipeline.factory import build_vlm_client, load_ocr_config

from .label_ocr_models import LabeledFigureAsset, ReviewedVisibleLabels, VisibleLabel
from .label_ocr_prompt import VISIBLE_LABEL_PROMPT_VERSION
from .label_ocr_review import review_visible_labels_bundle
from .label_ocr_runner import extract_visible_labels_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Figure Phase B3 visible-label OCR")
    commands = parser.add_subparsers(dest="command", required=True)

    propose = commands.add_parser("propose", help="create a pending B3 label proposal")
    propose.add_argument("--asset", type=Path, required=True)
    propose.add_argument("--out", type=Path, required=True)
    propose.add_argument("--config", type=Path)

    review = commands.add_parser("review", help="publish an explicit label review")
    review.add_argument("--asset", type=Path, required=True)
    review.add_argument("--out", type=Path, required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument(
        "--status",
        choices=("approved", "corrected", "rejected"),
        required=True,
    )
    review.add_argument(
        "--labels-json",
        type=Path,
        help="JSON array of {text, kind} objects; required only for corrected",
    )
    return parser


def _usage_error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def _load_source(asset_dir: Path) -> LabeledFigureAsset:
    return LabeledFigureAsset.model_validate_json(
        (asset_dir / "figure_asset.json").read_text(encoding="utf-8")
    )


def _source_proposal_id(asset: LabeledFigureAsset) -> str:
    proposal = asset.label_ocr.proposed
    prompt_version = proposal.prompt_version if proposal else asset.label_ocr.prompt_version
    if prompt_version is None:
        _usage_error("review requires a B3 prompt version")
    return f"{asset.asset_id}:{prompt_version}"


def _load_labels(path: Path) -> list[VisibleLabel]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _usage_error(f"cannot read --labels-json: {exc}")
    if not isinstance(payload, list):
        _usage_error("--labels-json root must be a JSON array")
    try:
        return TypeAdapter(list[VisibleLabel]).validate_python(payload)
    except ValidationError as exc:
        _usage_error(f"--labels-json violates the B3 label contract: {exc}")


def _run_propose(args: argparse.Namespace) -> int:
    config = load_ocr_config(args.config)
    label_config = config.get("figure_label_ocr") or {}
    max_new_tokens = int(label_config.get("max_new_tokens", 384))
    prompt_version = str(
        label_config.get("prompt_version", VISIBLE_LABEL_PROMPT_VERSION)
    )
    client = build_vlm_client(config)
    try:
        extract_visible_labels_bundle(
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
    if args.status == "approved":
        if args.labels_json is not None:
            _usage_error("approved review cannot use --labels-json")
    elif args.status == "corrected":
        if args.labels_json is None:
            _usage_error("corrected review requires --labels-json")
    elif args.labels_json is not None:
        _usage_error("rejected review cannot use --labels-json")

    asset = _load_source(args.asset)
    if args.status == "approved":
        proposal = asset.label_ocr.proposed
        if proposal is None:
            _usage_error("approved review requires a pending B3 proposal")
        labels = proposal.labels
    elif args.status == "corrected":
        labels = _load_labels(args.labels_json)
    else:
        labels = []

    decision = ReviewedVisibleLabels(
        labels=labels,
        status=args.status,
        reviewer=args.reviewer,
        source_proposal_id=_source_proposal_id(asset),
    )
    review_visible_labels_bundle(args.asset, args.out, decision)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "propose":
        return _run_propose(args)
    return _run_review(args)
