from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import figure_pipeline.workflow_cli as workflow_cli
from figure_pipeline.workflow import WorkflowPaths
from tests.figure_pipeline.test_classification_review import make_pending_b2_bundle
from tests.figure_pipeline.test_workflow import _place_b1, _place_pending_b2


def _commands() -> set[str]:
    parser = workflow_cli.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if action.__class__.__name__ == "_SubParsersAction"
    )
    return set(subparsers.choices)


def test_parser_exposes_exact_workflow_commands() -> None:
    assert _commands() == {
        "status",
        "b1-propose",
        "b1-preserve",
        "b2-propose",
        "b2-review",
        "b3-propose",
        "b3-review",
        "assemble",
    }


def test_status_prints_machine_readable_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "q018"

    assert workflow_cli.main(["status", "--root", str(root)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "next_command": "b1-propose",
        "reason": "no Figure workflow stage exists",
        "state": "needs_b1_proposal",
    }


def test_b2_propose_stops_at_human_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_b1(paths, tmp_path)
    source_pending = make_pending_b2_bundle(tmp_path / "pending-source")
    calls: list[list[str]] = []

    def fake_classification_main(argv: list[str]) -> int:
        calls.append(argv)
        assert argv[:2] == ["propose", "--asset"]
        shutil.copytree(source_pending, paths.b2_proposal)
        return 0

    def forbidden_stage(argv: list[str]) -> int:
        raise AssertionError(f"must stop before downstream stage: {argv}")

    monkeypatch.setattr(workflow_cli, "classification_main", fake_classification_main)
    monkeypatch.setattr(workflow_cli, "label_main", forbidden_stage)

    assert workflow_cli.main(["b2-propose", "--root", str(paths.root)]) == 0

    assert len(calls) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "awaiting_b2_review"
    assert payload["next_command"] == "b2-review"


def test_duplicate_b2_propose_fails_before_stage_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_pending_b2(paths, tmp_path)
    called = False

    def forbidden_stage(argv: list[str]) -> int:
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(workflow_cli, "classification_main", forbidden_stage)

    with pytest.raises(SystemExit) as exc:
        workflow_cli.main(["b2-propose", "--root", str(paths.root)])

    assert exc.value.code == 2
    assert called is False


@pytest.mark.parametrize("command", ["b3-propose", "assemble"])
def test_downstream_command_refuses_to_cross_review_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    paths = WorkflowPaths.for_root(tmp_path / "q018")
    _place_pending_b2(paths, tmp_path)
    label_called = False
    publish_called = False

    def forbidden_label(argv: list[str]) -> int:
        nonlocal label_called
        label_called = True
        return 0

    def forbidden_publish(**kwargs: object) -> Path:
        nonlocal publish_called
        publish_called = True
        return Path("never")

    monkeypatch.setattr(workflow_cli, "label_main", forbidden_label)
    monkeypatch.setattr(workflow_cli, "publish_reviewed_figures", forbidden_publish)
    argv = [command, "--root", str(paths.root)]
    if command == "assemble":
        argv.extend(["--pageir", str(tmp_path / "source.pageir.json")])

    with pytest.raises(SystemExit) as exc:
        workflow_cli.main(argv)

    assert exc.value.code == 2
    assert label_called is False
    assert publish_called is False
