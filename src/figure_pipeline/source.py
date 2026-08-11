from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .models import BBox, _valid_bbox

_DOC_RE = re.compile(r"^(?P<year>\d{4})p2$", re.IGNORECASE)


class QuestionSource(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    document_id: str
    parent_question_id: str
    source_pdf: str
    page: int
    question_id: int
    question_bbox: BBox
    crop_reference: str
    crop_path: Path


def load_question_source(layout_path: Path, *, question_id: int) -> QuestionSource:
    payload = json.loads(layout_path.read_text(encoding="utf-8"))
    pdf_path = Path(str(payload["pdf"]).replace("\\", "/"))
    match = _DOC_RE.fullmatch(pdf_path.stem)
    if match is None:
        raise ValueError(f"unsupported document identity: {pdf_path.stem}")
    document_id = f"hk-dse-{match.group('year')}-math-p2"

    matches: list[dict] = []
    for page in payload.get("pages", []):
        for block in page.get("blocks", []):
            if block.get("meta", {}).get("question_id") == question_id:
                matches.append(block)
    if len(matches) != 1:
        raise ValueError(
            f"expected one layout block for question {question_id}, got {len(matches)}"
        )

    block = matches[0]
    crop_path = Path(str(block["crop_path"]))
    if not crop_path.is_file():
        raise FileNotFoundError(crop_path)
    raw_bbox = tuple(float(value) for value in block["bbox"])
    if any(not value.is_integer() for value in raw_bbox):
        raise ValueError("question bbox must resolve to integer page pixels")
    bbox = _valid_bbox(tuple(int(value) for value in raw_bbox))
    parent_id = f"{document_id}-q{question_id:03d}"
    return QuestionSource(
        document_id=document_id,
        parent_question_id=parent_id,
        source_pdf=pdf_path.as_posix(),
        page=int(block["page"]),
        question_id=question_id,
        question_bbox=bbox,
        crop_reference=str(block["crop_path"]).replace("\\", "/"),
        crop_path=crop_path,
    )
