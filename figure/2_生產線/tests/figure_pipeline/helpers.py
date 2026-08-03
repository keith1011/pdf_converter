from __future__ import annotations

from typing import Any


def valid_asset_dict(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "pipeline_version": "figure-b1-v1",
        "document_id": "hk-dse-2015-math-p2",
        "asset_id": "hk-dse-2015-math-p2-q018-fig01",
        "parent_question_id": "hk-dse-2015-math-p2-q018",
        "asset_type": "figure",
        "figure_type": "unknown",
        "source": {
            "source_pdf": "1_收集資料/data/sources/2015p2.pdf",
            "page": 6,
            "original_question_crop_path": (
                "1_收集資料/data/pdf_pages/2015p2/crops/p006_q018.png"
            ),
            "question_crop_path": "question.png",
            "question_crop_sha256": "a" * 64,
            "question_bbox": [162, 1377, 1587, 2179],
            "question_bbox_space": "page_pixels",
            "crop_path": "assets/q018_fig01.png",
            "bbox": [700, 350, 1280, 760],
            "bbox_space": "question_crop_pixels",
            "sha256": "b" * 64,
        },
        "provenance": {
            "method": "mineru_confirmed",
            "detector": "mineru_pp_doclayout_v2",
            "detector_label": "image",
            "candidate_index": 0,
        },
        "visible_labels": [],
        "description": None,
        "entities": [],
        "relations": [],
        "validation": {"status": "pending", "reviewed": False},
    }
    data.update(overrides)
    return data
