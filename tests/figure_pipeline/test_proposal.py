from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from figure_pipeline.models import FigureProposal
from figure_pipeline.proposal import create_proposal_bundle
from figure_pipeline.source import QuestionSource


class FakeDetector:
    def detect(
        self, question_crop: Path, *, page: int
    ) -> list[FigureProposal]:
        assert question_crop.is_file()
        assert page == 6
        return [
            FigureProposal(
                bbox=(10, 20, 80, 70),
                label="image",
                detector="fake",
                confidence=0.9,
            )
        ]


def _source_for(crop_path: Path) -> QuestionSource:
    return QuestionSource(
        document_id="hk-dse-2015-math-p2",
        parent_question_id="hk-dse-2015-math-p2-q018",
        source_pdf="1_收集資料/data/sources/2015p2.pdf",
        page=6,
        question_id=18,
        question_bbox=(162, 1377, 1587, 2179),
        crop_reference="1_收集資料/data/pdf_pages/2015p2/crops/p006_q018.png",
        crop_path=crop_path,
    )


def test_create_proposal_bundle_writes_json_and_overlay(tmp_path: Path) -> None:
    crop_path = tmp_path / "question.png"
    Image.new("RGB", (100, 80), "white").save(crop_path)
    destination = tmp_path / "proposal"

    bundle = create_proposal_bundle(
        source=_source_for(crop_path),
        detector=FakeDetector(),
        destination=destination,
    )

    proposal_path = destination / "proposal.json"
    overlay_path = destination / "proposal_overlay.png"
    assert proposal_path.is_file()
    assert overlay_path.is_file()
    assert bundle.parent_question_id == "hk-dse-2015-math-p2-q018"
    assert bundle.question_crop_path == "1_收集資料/data/pdf_pages/2015p2/crops/p006_q018.png"
    assert bundle.question_crop_width == 100
    assert bundle.question_crop_height == 80
    assert bundle.proposals[0].bbox == (10, 20, 80, 70)

    payload = json.loads(proposal_path.read_text(encoding="utf-8"))
    assert payload == bundle.model_dump(mode="json")


def test_create_proposal_bundle_refuses_existing_destination(
    tmp_path: Path,
) -> None:
    crop_path = tmp_path / "question.png"
    Image.new("RGB", (100, 80), "white").save(crop_path)
    destination = tmp_path / "proposal"
    destination.mkdir()

    with pytest.raises(FileExistsError):
        create_proposal_bundle(
            source=_source_for(crop_path),
            detector=FakeDetector(),
            destination=destination,
        )
