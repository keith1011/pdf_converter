from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from .detectors.base import FigureDetector
from .models import ProposalBundle
from .source import QuestionSource


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_proposal_bundle(
    source: QuestionSource,
    detector: FigureDetector,
    destination: Path,
) -> ProposalBundle:
    if destination.exists():
        raise FileExistsError(destination)

    with Image.open(source.crop_path) as opened:
        image = opened.convert("RGB")
        image.load()

    proposals = detector.detect(source.crop_path, page=source.page)
    bundle = ProposalBundle(
        document_id=source.document_id,
        parent_question_id=source.parent_question_id,
        page=source.page,
        question_id=source.question_id,
        question_crop_path=source.crop_reference,
        question_crop_sha256=sha256_file(source.crop_path),
        question_crop_width=image.width,
        question_crop_height=image.height,
        proposals=proposals,
    )

    stage = destination.parent / (
        f".{destination.name}.staging-{uuid.uuid4().hex}"
    )
    stage.mkdir(parents=True)
    try:
        (stage / "proposal.json").write_text(
            json.dumps(
                bundle.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        draw = ImageDraw.Draw(image)
        for index, proposal in enumerate(proposals):
            draw.rectangle(proposal.bbox, outline="red", width=3)
            draw.text(
                (proposal.bbox[0] + 4, proposal.bbox[1] + 4),
                str(index),
                fill="red",
            )
        image.save(stage / "proposal_overlay.png")
        stage.rename(destination)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    return bundle
