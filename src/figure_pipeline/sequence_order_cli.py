from __future__ import annotations

import argparse
import json
import uuid
from collections.abc import Sequence
from pathlib import Path

from .sequence_order_evaluator import SequenceOrderReport, evaluate_sequence_order
from .sequence_order_metrics import SequenceGoldManifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate B3 visible-label sequence order against independent gold"
    )
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def _write_report(destination: Path, report: SequenceOrderReport) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.with_name(f".{destination.name}.staging-{uuid.uuid4().hex}")
    payload = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    try:
        stage.write_bytes((payload + "\n").encode("utf-8"))
        if destination.exists():
            raise FileExistsError(destination)
        stage.replace(destination)
    except Exception:
        stage.unlink(missing_ok=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = SequenceGoldManifest.model_validate_json(
        args.gold.read_text(encoding="utf-8")
    )
    report = evaluate_sequence_order(manifest, args.benchmark_root)
    _write_report(args.out, report)
    return 0
