from __future__ import annotations

import pytest
from pydantic import ValidationError

from figure_pipeline.models import FigureAsset
from tests.figure_pipeline.helpers import valid_asset_dict


def test_figure_asset_accepts_phase_b1_contract() -> None:
    asset = FigureAsset.model_validate(valid_asset_dict())

    assert asset.asset_id == "hk-dse-2015-math-p2-q018-fig01"
    assert asset.source.bbox_space == "question_crop_pixels"
    assert asset.validation.status == "pending"
    assert asset.validation.reviewed is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("asset_id", "hk-dse-2015-math-p2-q019-fig01"),
        ("asset_id", "q018-fig01"),
        ("figure_type", "geometry"),
    ],
)
def test_figure_asset_rejects_invalid_phase_b1_identity(field: str, value: str) -> None:
    data = valid_asset_dict()
    data[field] = value

    with pytest.raises(ValidationError):
        FigureAsset.model_validate(data)


def test_figure_asset_rejects_invalid_hash_and_bbox() -> None:
    data = valid_asset_dict()
    data["source"]["sha256"] = "not-a-hash"
    data["source"]["bbox"] = [10, 10, 10, 20]

    with pytest.raises(ValidationError):
        FigureAsset.model_validate(data)


@pytest.mark.parametrize("field", ["crop_path", "question_crop_path"])
@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/outside/crop.png",
        r"C:\outside\crop.png",
        r"C:outside\crop.png",
        r"\outside\crop.png",
        r"\\server\share\crop.png",
    ],
)
def test_figure_asset_rejects_paths_outside_bundle(
    field: str,
    unsafe_path: str,
) -> None:
    data = valid_asset_dict()
    data["source"][field] = unsafe_path

    with pytest.raises(ValidationError):
        FigureAsset.model_validate(data)


def test_manual_provenance_rejects_detector_fields() -> None:
    data = valid_asset_dict()
    data["provenance"] = {
        "method": "manual",
        "detector": "mineru_pp_doclayout_v2",
        "detector_label": None,
        "candidate_index": None,
    }

    with pytest.raises(ValidationError):
        FigureAsset.model_validate(data)
