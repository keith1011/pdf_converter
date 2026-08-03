from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .detectors.base import FigureDetector
from .detectors.mineru import MineruFigureDetector
from .models import ProposalBundle
from .preserve import preserve_asset
from .proposal import create_proposal_bundle
from .source import load_question_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Figure Phase B1 preservation")
    commands = parser.add_subparsers(dest="command", required=True)

    propose = commands.add_parser("propose")
    propose.add_argument("--layout", type=Path, required=True)
    propose.add_argument("--question-id", type=int, required=True)
    propose.add_argument("--out", type=Path, required=True)

    preserve = commands.add_parser("preserve")
    preserve.add_argument("--layout", type=Path, required=True)
    preserve.add_argument("--question-id", type=int, required=True)
    preserve.add_argument("--proposal", type=Path)
    preserve.add_argument("--candidate", type=int)
    preserve.add_argument("--manual-bbox", type=int, nargs=4)
    preserve.add_argument("--out", type=Path, required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    detector: FigureDetector | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    source = load_question_source(args.layout, question_id=args.question_id)

    if args.command == "propose":
        create_proposal_bundle(
            source,
            detector or MineruFigureDetector(),
            args.out,
        )
        return 0

    if args.manual_bbox is not None:
        if args.proposal is not None or args.candidate is not None:
            raise SystemExit(
                "--manual-bbox cannot be combined with --proposal/--candidate"
            )
        preserve_asset(
            source=source,
            destination=args.out,
            manual_bbox=tuple(args.manual_bbox),
        )
        return 0

    if args.proposal is None or args.candidate is None:
        raise SystemExit(
            "preserve requires --proposal and --candidate, or --manual-bbox"
        )
    bundle = ProposalBundle.model_validate_json(
        args.proposal.read_text(encoding="utf-8")
    )
    preserve_asset(
        source=source,
        destination=args.out,
        proposal_bundle=bundle,
        candidate_index=args.candidate,
    )
    return 0
