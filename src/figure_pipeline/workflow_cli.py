from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .classification_cli import VISUAL_FAMILIES
from .classification_cli import main as classification_main
from .cli import main as b1_main
from .label_ocr_cli import main as label_main
from .publish import publish_reviewed_figures
from .workflow import WorkflowPaths, WorkflowStatus, inspect_workflow


def _add_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review-gated Figure workflow")
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status")
    _add_root(status)

    b1_propose = commands.add_parser("b1-propose")
    _add_root(b1_propose)
    b1_propose.add_argument("--layout", type=Path, required=True)
    b1_propose.add_argument("--question-id", type=int, required=True)

    b1_preserve = commands.add_parser("b1-preserve")
    _add_root(b1_preserve)
    b1_preserve.add_argument("--layout", type=Path, required=True)
    b1_preserve.add_argument("--question-id", type=int, required=True)
    b1_choice = b1_preserve.add_mutually_exclusive_group(required=True)
    b1_choice.add_argument("--candidate", type=int)
    b1_choice.add_argument("--manual-bbox", type=int, nargs=4)

    b2_propose = commands.add_parser("b2-propose")
    _add_root(b2_propose)
    b2_propose.add_argument("--config", type=Path)

    b2_review = commands.add_parser("b2-review")
    _add_root(b2_review)
    b2_review.add_argument("--reviewer", required=True)
    b2_review.add_argument(
        "--status",
        choices=("approved", "corrected", "rejected"),
        required=True,
    )
    b2_review.add_argument("--visual-family", choices=VISUAL_FAMILIES)
    b2_review.add_argument("--subtype")
    b2_review.add_argument(
        "--secondary-tag",
        action="append",
        choices=VISUAL_FAMILIES,
        default=[],
    )

    b3_propose = commands.add_parser("b3-propose")
    _add_root(b3_propose)
    b3_propose.add_argument("--config", type=Path)

    b3_review = commands.add_parser("b3-review")
    _add_root(b3_review)
    b3_review.add_argument("--reviewer", required=True)
    b3_review.add_argument(
        "--status",
        choices=("approved", "corrected", "rejected"),
        required=True,
    )
    b3_review.add_argument("--labels-json", type=Path)

    assemble = commands.add_parser("assemble")
    _add_root(assemble)
    assemble.add_argument("--pageir", type=Path, required=True)
    return parser


def _usage_error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_state(root: Path, *allowed: str) -> WorkflowStatus:
    status = inspect_workflow(root)
    if status.state not in allowed:
        expected = ", ".join(allowed)
        _usage_error(
            f"workflow state is {status.state}; command requires {expected}"
        )
    return status


def _emit_status(root: Path) -> None:
    status = inspect_workflow(root)
    print(json.dumps(status.model_dump(mode="json"), sort_keys=True))


def _run_b1_propose(args: argparse.Namespace, paths: WorkflowPaths) -> None:
    _require_state(paths.root, "needs_b1_proposal")
    b1_main(
        [
            "propose",
            "--layout",
            str(args.layout),
            "--question-id",
            str(args.question_id),
            "--out",
            str(paths.b1_proposal),
        ]
    )


def _run_b1_preserve(args: argparse.Namespace, paths: WorkflowPaths) -> None:
    if args.candidate is not None:
        _require_state(paths.root, "awaiting_b1_selection")
    else:
        _require_state(paths.root, "needs_b1_proposal", "awaiting_b1_selection")
    argv = [
        "preserve",
        "--layout",
        str(args.layout),
        "--question-id",
        str(args.question_id),
        "--out",
        str(paths.b1_asset),
    ]
    if args.candidate is not None:
        argv.extend(
            [
                "--proposal",
                str(paths.b1_proposal / "proposal.json"),
                "--candidate",
                str(args.candidate),
            ]
        )
    else:
        argv.extend(["--manual-bbox", *(str(value) for value in args.manual_bbox)])
    b1_main(argv)


def _run_b2_propose(args: argparse.Namespace, paths: WorkflowPaths) -> None:
    _require_state(paths.root, "ready_for_b2")
    argv = [
        "propose",
        "--asset",
        str(paths.b1_asset),
        "--out",
        str(paths.b2_proposal),
    ]
    if args.config is not None:
        argv.extend(["--config", str(args.config)])
    classification_main(argv)


def _run_b2_review(args: argparse.Namespace, paths: WorkflowPaths) -> None:
    _require_state(paths.root, "awaiting_b2_review")
    argv = [
        "review",
        "--asset",
        str(paths.b2_proposal),
        "--out",
        str(paths.b2_reviewed),
        "--reviewer",
        args.reviewer,
        "--status",
        args.status,
    ]
    if args.visual_family is not None:
        argv.extend(["--visual-family", args.visual_family])
    if args.subtype is not None:
        argv.extend(["--subtype", args.subtype])
    for tag in args.secondary_tag:
        argv.extend(["--secondary-tag", tag])
    classification_main(argv)


def _run_b3_propose(args: argparse.Namespace, paths: WorkflowPaths) -> None:
    _require_state(paths.root, "ready_for_b3")
    argv = [
        "propose",
        "--asset",
        str(paths.b2_reviewed),
        "--out",
        str(paths.b3_proposal),
    ]
    if args.config is not None:
        argv.extend(["--config", str(args.config)])
    label_main(argv)


def _run_b3_review(args: argparse.Namespace, paths: WorkflowPaths) -> None:
    _require_state(paths.root, "awaiting_b3_review")
    argv = [
        "review",
        "--asset",
        str(paths.b3_proposal),
        "--out",
        str(paths.b3_reviewed),
        "--reviewer",
        args.reviewer,
        "--status",
        args.status,
    ]
    if args.labels_json is not None:
        argv.extend(["--labels-json", str(args.labels_json)])
    label_main(argv)


def _run_assemble(args: argparse.Namespace, paths: WorkflowPaths) -> None:
    _require_state(paths.root, "ready_for_assembly")
    publish_reviewed_figures(
        pageir_path=args.pageir,
        bundle_dirs=[paths.b3_reviewed],
        destination=paths.assembled,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        _emit_status(args.root)
        return 0

    paths = WorkflowPaths.for_root(args.root)
    runners = {
        "b1-propose": _run_b1_propose,
        "b1-preserve": _run_b1_preserve,
        "b2-propose": _run_b2_propose,
        "b2-review": _run_b2_review,
        "b3-propose": _run_b3_propose,
        "b3-review": _run_b3_review,
        "assemble": _run_assemble,
    }
    runners[args.command](args, paths)
    _emit_status(paths.root)
    return 0
