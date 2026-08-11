from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import figure_pipeline.pageir as pageir_module
import figure_pipeline.publish as publish_module
from figure_pipeline.publish import publish_reviewed_figures
from ocr_pipeline import figure_export
from tests.figure_pipeline.test_pageir import make_reviewed_b3_bundle
from tests.figure_pipeline.test_publish import _write_pageir


def test_reviewed_pageir_and_publish_exclude_legacy_figure_export() -> None:
    for module in (pageir_module, publish_module):
        assert "figure_export" not in inspect.getsource(module)


def test_reviewed_publish_does_not_call_legacy_vlm_caption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_legacy_export(*args: object, **kwargs: object) -> None:
        raise AssertionError("reviewed publish called legacy figure_export")

    monkeypatch.setattr(figure_export, "export_figures", fail_legacy_export)
    pageir_path = tmp_path / "2015p2.pageir.json"
    _write_pageir(pageir_path)
    bundle = make_reviewed_b3_bundle(tmp_path / "source")

    output_path = publish_reviewed_figures(
        pageir_path=pageir_path,
        bundle_dirs=[bundle],
        destination=tmp_path / "assembled",
    )

    assert output_path.is_file()
