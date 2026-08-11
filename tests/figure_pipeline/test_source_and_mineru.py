from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from figure_pipeline.detectors.mineru import MineruFigureDetector
from figure_pipeline.source import load_question_source
from ocr_pipeline.models import BBox, BlockType, LayoutBlock


def test_load_question_source_uses_stage1_identity(tmp_path: Path) -> None:
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
                                "block_id": "p006_q018",
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

    source = load_question_source(layout, question_id=18)

    assert source.parent_question_id == "hk-dse-2015-math-p2-q018"
    assert source.page == 6
    assert source.question_bbox == (10, 20, 110, 100)
    assert source.crop_path == crop


def test_mineru_detector_returns_only_valid_figure_blocks(
    tmp_path: Path,
) -> None:
    crop = tmp_path / "crop.png"
    Image.new("RGB", (100, 80), "white").save(crop)

    class FakeEngine:
        def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]:
            return [
                LayoutBlock(
                    "text",
                    BlockType.TEXT,
                    BBox(1, 1, 20, 20),
                    0,
                    page,
                    image_path,
                ),
                LayoutBlock(
                    "figure",
                    BlockType.FIGURE,
                    BBox(10.2, 11.8, 90.1, 70.2),
                    1,
                    page,
                    image_path,
                    meta={"label": "image"},
                ),
                LayoutBlock(
                    "outside",
                    BlockType.FIGURE,
                    BBox(10, 10, 120, 70),
                    2,
                    page,
                    image_path,
                    meta={"label": "chart"},
                ),
            ]

    proposals = MineruFigureDetector(engine=FakeEngine()).detect(crop, page=6)

    assert [p.bbox for p in proposals] == [(10, 11, 91, 71)]
    assert proposals[0].label == "image"
    assert proposals[0].detector == "mineru_pp_doclayout_v2"
