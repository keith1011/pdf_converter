from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from figure_pipeline.cli import main
from figure_pipeline.models import FigureProposal


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
            )
        ]


def write_layout(tmp_path: Path) -> Path:
    crop = tmp_path / "crop.png"
    page = tmp_path / "page.png"
    Image.new("RGB", (100, 80), "white").save(crop)
    Image.new("RGB", (200, 200), "white").save(page)
    layout = tmp_path / "layout.json"
    layout.write_text(
        json.dumps(
            {
                "pdf": "1_收集資料/data/sources/2015p2.pdf",
                "pages": [
                    {
                        "page": 6,
                        "blocks": [
                            {
                                "bbox": [10, 20, 110, 100],
                                "page": 6,
                                "image_path": str(page),
                                "crop_path": str(crop),
                                "meta": {"question_id": 18},
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return layout


def test_cli_propose_writes_proposal_bundle(tmp_path: Path) -> None:
    out = tmp_path / "proposal"
    exit_code = main(
        [
            "propose",
            "--layout",
            str(write_layout(tmp_path)),
            "--question-id",
            "18",
            "--out",
            str(out),
        ],
        detector=FakeDetector(),
    )

    assert exit_code == 0
    assert (out / "proposal.json").is_file()


def test_cli_preserve_manual_writes_asset_bundle(tmp_path: Path) -> None:
    out = tmp_path / "final"
    exit_code = main(
        [
            "preserve",
            "--layout",
            str(write_layout(tmp_path)),
            "--question-id",
            "18",
            "--manual-bbox",
            "10",
            "20",
            "80",
            "70",
            "--out",
            str(out),
        ]
    )

    assert exit_code == 0
    assert (out / "figure_asset.json").is_file()
