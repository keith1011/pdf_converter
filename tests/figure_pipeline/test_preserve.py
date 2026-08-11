from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from figure_pipeline.models import FigureProposal, ProposalBundle
from figure_pipeline.preserve import preserve_asset
from figure_pipeline.proposal import sha256_file
from figure_pipeline.source import QuestionSource


def make_source(tmp_path: Path) -> QuestionSource:
    crop = tmp_path / "upstream-question.png"
    Image.new("RGB", (100, 80), "white").save(crop)
    return QuestionSource(
        document_id="hk-dse-2015-math-p2",
        parent_question_id="hk-dse-2015-math-p2-q018",
        source_pdf="1_收集資料/data/sources/2015p2.pdf",
        page=6,
        question_id=18,
        question_bbox=(162, 1377, 1587, 2179),
        crop_reference="1_收集資料/data/pdf_pages/2015p2/crops/p006_q018.png",
        crop_path=crop,
    )


def make_bundle(source: QuestionSource) -> ProposalBundle:
    return ProposalBundle(
        document_id=source.document_id,
        parent_question_id=source.parent_question_id,
        page=source.page,
        question_id=source.question_id,
        question_crop_path=source.crop_reference,
        question_crop_sha256=sha256_file(source.crop_path),
        question_crop_width=100,
        question_crop_height=80,
        proposals=[
            FigureProposal(
                bbox=(10, 20, 80, 70),
                label="image",
                detector="mineru_pp_doclayout_v2",
            )
        ],
    )


def test_preserve_confirmed_proposal_writes_verified_bundle(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    out = tmp_path / "final"

    asset = preserve_asset(
        source=source,
        destination=out,
        proposal_bundle=make_bundle(source),
        candidate_index=0,
    )

    figure = out / asset.source.crop_path
    question = out / asset.source.question_crop_path
    assert figure.is_file()
    assert question.read_bytes() == source.crop_path.read_bytes()
    assert sha256_file(figure) == asset.source.sha256
    assert sha256_file(question) == asset.source.question_crop_sha256
    saved = json.loads(
        (out / "figure_asset.json").read_text(encoding="utf-8")
    )
    assert saved["parent_question_id"] == "hk-dse-2015-math-p2-q018"
    assert saved["provenance"]["method"] == "mineru_confirmed"


def test_preserve_manual_bbox_uses_same_schema(tmp_path: Path) -> None:
    source = make_source(tmp_path)

    asset = preserve_asset(
        source=source,
        destination=tmp_path / "manual",
        manual_bbox=(10, 20, 80, 70),
    )

    assert asset.provenance.method == "manual"
    assert asset.source.bbox == (10, 20, 80, 70)


@pytest.mark.parametrize(
    "bbox",
    [
        (10, 10, 10, 20),
        (-1, 0, 20, 20),
        (0, 0, 101, 80),
    ],
)
def test_preserve_rejects_invalid_bbox_without_final_bundle(
    tmp_path: Path, bbox: tuple[int, int, int, int]
) -> None:
    source = make_source(tmp_path)
    out = tmp_path / "invalid"

    with pytest.raises(ValueError):
        preserve_asset(source=source, destination=out, manual_bbox=bbox)

    assert not out.exists()


def test_preserve_refuses_existing_destination(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    out = tmp_path / "existing"
    out.mkdir()

    with pytest.raises(FileExistsError):
        preserve_asset(
            source=source,
            destination=out,
            manual_bbox=(10, 20, 80, 70),
        )


def test_preserve_rejects_proposal_for_different_question(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    out = tmp_path / "mismatch"
    bundle = make_bundle(source).model_copy(update={"question_id": 19})

    with pytest.raises(ValueError, match="does not match"):
        preserve_asset(
            source=source,
            destination=out,
            proposal_bundle=bundle,
            candidate_index=0,
        )

    assert not out.exists()
