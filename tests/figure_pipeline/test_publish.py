from __future__ import annotations

import json
from pathlib import Path

import pytest

import figure_pipeline.publish as publish_module
from figure_pipeline.pageir import load_publishable_asset
from figure_pipeline.proposal import sha256_file
from figure_pipeline.publish import publish_reviewed_figures
from tests.figure_pipeline.test_label_ocr_runner import snapshot_tree
from tests.figure_pipeline.test_pageir import make_reviewed_b3_bundle


def _write_pageir(path: Path, *, anchors: list[str] | None = None) -> None:
    anchors = ["p006_q018"] if anchors is None else anchors
    payload = {
        "pages": [
            {
                "page_index": 6,
                "segments": [
                    {
                        "kind": "prose",
                        "text": f"question {index}",
                        "source_block_id": anchor,
                        "bbox": [0, 0, 100, 100],
                        "integrity": "ok",
                        "crop_relpath": None,
                        "version_id": None,
                    }
                    for index, anchor in enumerate(anchors)
                ],
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_publish_inserts_reviewed_figure_and_preserves_inputs(tmp_path: Path) -> None:
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    pageir_before = pageir_path.read_bytes()
    bundle_before = snapshot_tree(bundle)
    asset = load_publishable_asset(bundle)
    destination = tmp_path / "assembled"

    output_path = publish_reviewed_figures(
        pageir_path=pageir_path,
        bundle_dirs=[bundle],
        destination=destination,
    )

    assert output_path == destination / pageir_path.name
    assert pageir_path.read_bytes() == pageir_before
    assert snapshot_tree(bundle) == bundle_before
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    source_ids = [segment["source_block_id"] for segment in payload["pages"][0]["segments"]]
    assert source_ids == ["p006_q018", asset.asset_id]
    figure = payload["pages"][0]["segments"][1]
    expected_relpath = f"figures/{asset.asset_id}-{asset.source.sha256[:12]}.png"
    assert figure["crop_relpath"] == expected_relpath
    copied_crop = destination / expected_relpath
    assert sha256_file(copied_crop) == asset.source.sha256
    assert list(tmp_path.glob(".assembled.staging-*")) == []


def test_existing_destination_is_preserved(tmp_path: Path) -> None:
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    destination = tmp_path / "assembled"
    destination.mkdir()
    sentinel = destination / "sentinel.bin"
    sentinel.write_bytes(b"keep")

    with pytest.raises(FileExistsError):
        publish_reviewed_figures(
            pageir_path=pageir_path,
            bundle_dirs=[bundle],
            destination=destination,
        )

    assert sentinel.read_bytes() == b"keep"


@pytest.mark.parametrize(
    "anchors",
    [[], ["p006_q018", "p006_q018"]],
    ids=["missing", "duplicate"],
)
def test_question_anchor_must_be_unique(tmp_path: Path, anchors: list[str]) -> None:
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path, anchors=anchors)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    destination = tmp_path / "assembled"

    with pytest.raises(ValueError, match="anchor"):
        publish_reviewed_figures(
            pageir_path=pageir_path,
            bundle_dirs=[bundle],
            destination=destination,
        )

    assert not destination.exists()
    assert list(tmp_path.glob(".assembled.staging-*")) == []


def test_pageir_document_must_match_figure_document(tmp_path: Path) -> None:
    pageir_path = tmp_path / "2016p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    destination = tmp_path / "assembled"

    with pytest.raises(ValueError, match="document"):
        publish_reviewed_figures(
            pageir_path=pageir_path,
            bundle_dirs=[bundle],
            destination=destination,
        )

    assert not destination.exists()


def test_duplicate_asset_id_is_rejected_before_staging(tmp_path: Path) -> None:
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    destination = tmp_path / "assembled"

    with pytest.raises(ValueError, match="duplicate asset_id"):
        publish_reviewed_figures(
            pageir_path=pageir_path,
            bundle_dirs=[bundle, bundle],
            destination=destination,
        )

    assert not destination.exists()


def test_asset_already_present_in_pageir_is_rejected(tmp_path: Path) -> None:
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    asset = load_publishable_asset(bundle)
    payload = json.loads(pageir_path.read_text(encoding="utf-8"))
    payload["pages"][0]["segments"].append(
        {
            "kind": "figure",
            "text": "already present",
            "source_block_id": asset.asset_id,
            "bbox": [0, 0, 1, 1],
            "integrity": "ok",
            "crop_relpath": "figures/already.png",
            "version_id": "old",
        }
    )
    pageir_path.write_text(json.dumps(payload), encoding="utf-8")
    destination = tmp_path / "assembled"

    with pytest.raises(ValueError, match="already contains asset_id"):
        publish_reviewed_figures(
            pageir_path=pageir_path,
            bundle_dirs=[bundle],
            destination=destination,
        )

    assert not destination.exists()


def test_tampered_crop_fails_before_staging(tmp_path: Path) -> None:
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    asset = load_publishable_asset(bundle)
    (bundle / asset.source.crop_path).write_bytes(b"tampered")
    destination = tmp_path / "assembled"

    with pytest.raises(ValueError, match="figure crop hash"):
        publish_reviewed_figures(
            pageir_path=pageir_path,
            bundle_dirs=[bundle],
            destination=destination,
        )

    assert not destination.exists()
    assert list(tmp_path.glob(".assembled.staging-*")) == []


def test_corrupted_crop_copy_is_rejected_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    destination = tmp_path / "assembled"

    def corrupt_copy(source: Path, target: Path) -> Path:
        target.write_bytes(b"corrupted-after-validation")
        return target

    monkeypatch.setattr(publish_module.shutil, "copy2", corrupt_copy)

    with pytest.raises(ValueError, match="copied figure crop hash"):
        publish_reviewed_figures(
            pageir_path=pageir_path,
            bundle_dirs=[bundle],
            destination=destination,
        )

    assert not destination.exists()
    assert list(tmp_path.glob(".assembled.staging-*")) == []


def test_write_failure_removes_only_operation_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    destination = tmp_path / "assembled"
    original_write_text = Path.write_text

    def fail_stage_write(path: Path, data: str, **kwargs: object) -> int:
        if path.parent.name.startswith(".assembled.staging-"):
            raise OSError("pageir write failed")
        return original_write_text(path, data, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_stage_write)

    with pytest.raises(OSError, match="pageir write failed"):
        publish_reviewed_figures(
            pageir_path=pageir_path,
            bundle_dirs=[bundle],
            destination=destination,
        )

    assert not destination.exists()
    assert list(tmp_path.glob(".assembled.staging-*")) == []


def test_rename_failure_removes_only_operation_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")
    destination = tmp_path / "assembled"

    def fail_rename(source: Path, target: Path) -> Path:
        raise OSError(f"rename failed: {source} -> {target}")

    monkeypatch.setattr(Path, "rename", fail_rename)

    with pytest.raises(OSError, match="rename failed"):
        publish_reviewed_figures(
            pageir_path=pageir_path,
            bundle_dirs=[bundle],
            destination=destination,
        )

    assert not destination.exists()
    assert list(tmp_path.glob(".assembled.staging-*")) == []
