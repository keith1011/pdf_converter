from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from PIL import Image

from .models import (
    AssetProvenance,
    AssetSource,
    FigureAsset,
    ProposalBundle,
)
from .proposal import sha256_file
from .source import QuestionSource


def _validate_bbox(
    bbox: tuple[int, int, int, int],
    *,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    if min(bbox) < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError("bbox must be non-negative and non-empty")
    if x2 > width or y2 > height:
        raise ValueError("bbox is outside question crop")
    return bbox


def _confirmed_bbox(
    source: QuestionSource,
    bundle: ProposalBundle,
    candidate_index: int,
) -> tuple[tuple[int, int, int, int], AssetProvenance]:
    with Image.open(source.crop_path) as image:
        width, height = image.size
    expected_hash = sha256_file(source.crop_path)
    checks = (
        bundle.document_id == source.document_id,
        bundle.parent_question_id == source.parent_question_id,
        bundle.page == source.page,
        bundle.question_id == source.question_id,
        bundle.question_crop_path == source.crop_reference,
        bundle.question_crop_sha256 == expected_hash,
        bundle.question_crop_width == width,
        bundle.question_crop_height == height,
    )
    if not all(checks):
        raise ValueError("proposal metadata does not match question source")
    try:
        proposal = bundle.proposals[candidate_index]
    except IndexError as exc:
        raise ValueError("candidate index is out of range") from exc
    return proposal.bbox, AssetProvenance(
        method="mineru_confirmed",
        detector=proposal.detector,
        detector_label=proposal.label,
        candidate_index=candidate_index,
    )


def preserve_asset(
    *,
    source: QuestionSource,
    destination: Path,
    proposal_bundle: ProposalBundle | None = None,
    candidate_index: int | None = None,
    manual_bbox: tuple[int, int, int, int] | None = None,
) -> FigureAsset:
    if destination.exists():
        raise FileExistsError(destination)
    confirmed = proposal_bundle is not None or candidate_index is not None
    if confirmed == (manual_bbox is not None):
        raise ValueError("choose exactly one of confirmed proposal or manual bbox")
    if proposal_bundle is not None and candidate_index is not None:
        bbox, provenance = _confirmed_bbox(
            source, proposal_bundle, candidate_index
        )
    elif manual_bbox is not None:
        bbox = manual_bbox
        provenance = AssetProvenance(method="manual")
    else:
        raise ValueError(
            "proposal bundle and candidate index must be supplied together"
        )

    with Image.open(source.crop_path) as opened:
        question_image = opened.convert("RGB")
        question_image.load()
    bbox = _validate_bbox(
        bbox,
        width=question_image.width,
        height=question_image.height,
    )

    stage = destination.parent / (
        f".{destination.name}.staging-{uuid.uuid4().hex}"
    )
    stage.mkdir(parents=True)
    try:
        question_path = stage / "question.png"
        shutil.copy2(source.crop_path, question_path)
        source_question_hash = sha256_file(source.crop_path)
        if sha256_file(question_path) != source_question_hash:
            raise RuntimeError("question crop hash mismatch")

        asset_dir = stage / "assets"
        asset_dir.mkdir()
        figure_name = f"q{source.question_id:03d}_fig01.png"
        figure_path = asset_dir / figure_name
        question_image.crop(bbox).save(figure_path)
        figure_hash = sha256_file(figure_path)

        asset = FigureAsset(
            document_id=source.document_id,
            asset_id=f"{source.parent_question_id}-fig01",
            parent_question_id=source.parent_question_id,
            source=AssetSource(
                source_pdf=source.source_pdf,
                page=source.page,
                original_question_crop_path=source.crop_reference,
                question_crop_path="question.png",
                question_crop_sha256=source_question_hash,
                question_bbox=source.question_bbox,
                crop_path=f"assets/{figure_name}",
                bbox=bbox,
                sha256=figure_hash,
            ),
            provenance=provenance,
        )
        json_path = stage / "figure_asset.json"
        json_path.write_text(
            json.dumps(
                asset.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        round_trip = FigureAsset.model_validate_json(
            json_path.read_text(encoding="utf-8")
        )
        if (
            sha256_file(stage / round_trip.source.crop_path)
            != round_trip.source.sha256
        ):
            raise RuntimeError("figure crop hash mismatch")
        stage.rename(destination)
        return round_trip
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
