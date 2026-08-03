# Figure Phase B1 Asset Preservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve one human-confirmed figure from HKDSE 2015 Mathematics
Paper 2 Question 18 as a traceable crop and validated `FigureAsset` JSON.

**Architecture:** Add an isolated `figure_pipeline` package. MinerU produces
figure bbox proposals on the existing question crop; a human explicitly
accepts one proposal, with manual bbox as fallback. A preservation service
stages the question crop, figure crop and JSON, verifies hashes, then publishes
the bundle without modifying Track A.

**Tech Stack:** Python 3.12, Pydantic v2, Pillow, existing MinerU
`MineruLayoutEngine`, pytest, uv.

**Design spec:** `3.分析結果/docs/superpowers/specs/2026-07-31-figure-phase-b1-asset-preservation-design.md`

**Commit policy:** This workspace forbids commit, stage, push and PR creation
without explicit user approval. Commit steps are intentionally omitted.

---

## File structure

Create:

```text
2_生產線/src/figure_pipeline/
├── __init__.py                 Public Phase B1 exports
├── models.py                   FigureAsset, source, provenance and proposal schemas
├── source.py                   Read one question from Track A layout.json
├── proposal.py                 Proposal JSON and overlay generation
├── preserve.py                 Atomic crop/hash/asset-bundle publication
├── cli.py                      Argument parsing and command orchestration
└── detectors/
    ├── __init__.py
    ├── base.py                 Detector protocol
    └── mineru.py               Read-only adapter around MineruLayoutEngine

2_生產線/_script/
└── phase_b1_figure_asset.py    Thin executable entry point

2_生產線/tests/figure_pipeline/
├── __init__.py
├── helpers.py
├── test_models.py
├── test_source_and_mineru.py
├── test_proposal.py
├── test_preserve.py
└── test_cli.py

3.分析結果/docs/figure_pipeline/
└── progress.md                 Figure-only implementation evidence
```

Modify:

```text
pyproject.toml                  Include 2_生產線/src/figure_pipeline in wheel packages
```

Do not modify:

```text
2_生產線/src/ocr_pipeline/**
2_生產線/tests/test_mcq_*.py
3.分析結果/reports/handoff_ocr.md
```

---

### Task 1: Define strict Phase B1 schemas

**Files:**

- Create: `2_生產線/src/figure_pipeline/__init__.py`
- Create: `2_生產線/src/figure_pipeline/models.py`
- Create: `2_生產線/tests/figure_pipeline/__init__.py`
- Create: `2_生產線/tests/figure_pipeline/helpers.py`
- Create: `2_生產線/tests/figure_pipeline/test_models.py`

- [ ] **Step 1: Write the shared test factory**

Create `2_生產線/tests/figure_pipeline/helpers.py`:

```python
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
```

- [ ] **Step 2: Write failing schema tests**

Create `2_生產線/tests/figure_pipeline/test_models.py`:

```python
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
def test_figure_asset_rejects_invalid_phase_b1_identity(
    field: str, value: str
) -> None:
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
```

- [ ] **Step 3: Run the tests and verify RED**

Run:

```powershell
uv run python -m pytest 2_生產線/tests/figure_pipeline/test_models.py -q `
  -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b1-models
```

Expected: collection fails with
`ModuleNotFoundError: No module named 'figure_pipeline'`.

- [ ] **Step 4: Implement the strict models**

Create `2_生產線/src/figure_pipeline/models.py`:

```python
from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

BBox = tuple[StrictInt, StrictInt, StrictInt, StrictInt]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DOCUMENT_ID_RE = re.compile(r"^hk-dse-\d{4}-math-p2$")
_QUESTION_ID_RE = re.compile(r"^hk-dse-\d{4}-math-p2-q\d{3}$")
_ASSET_ID_RE = re.compile(r"^hk-dse-\d{4}-math-p2-q\d{3}-fig\d{2}$")


def _valid_bbox(value: BBox) -> BBox:
    x1, y1, x2, y2 = value
    if min(value) < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError("bbox must be non-negative and non-empty")
    return value


def _valid_sha256(value: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
    return value


def _valid_relative_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        raise ValueError("path must be a non-empty safe relative path")
    return path.as_posix()


def _valid_source_reference(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        raise ValueError("source reference cannot be empty")
    return normalized


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetValidation(StrictModel):
    status: Literal["pending"] = "pending"
    reviewed: Literal[False] = False


class AssetProvenance(StrictModel):
    method: Literal["mineru_confirmed", "manual"]
    detector: str | None = None
    detector_label: str | None = None
    candidate_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_method_fields(self) -> "AssetProvenance":
        if self.method == "manual":
            if any(
                value is not None
                for value in (
                    self.detector,
                    self.detector_label,
                    self.candidate_index,
                )
            ):
                raise ValueError("manual provenance cannot contain detector fields")
        elif not self.detector or not self.detector_label:
            raise ValueError("confirmed MinerU provenance requires detector fields")
        elif self.candidate_index is None:
            raise ValueError("confirmed MinerU provenance requires candidate_index")
        return self


class AssetSource(StrictModel):
    source_pdf: str
    page: int = Field(ge=1)
    original_question_crop_path: str
    question_crop_path: str
    question_crop_sha256: str
    question_bbox: BBox
    question_bbox_space: Literal["page_pixels"] = "page_pixels"
    crop_path: str
    bbox: BBox
    bbox_space: Literal["question_crop_pixels"] = "question_crop_pixels"
    sha256: str

    _validate_question_bbox = field_validator("question_bbox")(_valid_bbox)
    _validate_bbox = field_validator("bbox")(_valid_bbox)
    _validate_question_hash = field_validator("question_crop_sha256")(
        _valid_sha256
    )
    _validate_crop_hash = field_validator("sha256")(_valid_sha256)
    _validate_source_references = field_validator(
        "source_pdf", "original_question_crop_path"
    )(_valid_source_reference)
    _validate_bundle_paths = field_validator(
        "question_crop_path", "crop_path"
    )(_valid_relative_path)


class FigureProposal(StrictModel):
    bbox: BBox
    bbox_space: Literal["question_crop_pixels"] = "question_crop_pixels"
    label: str = Field(min_length=1)
    detector: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    _validate_bbox = field_validator("bbox")(_valid_bbox)


class ProposalBundle(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    document_id: str
    parent_question_id: str
    page: int = Field(ge=1)
    question_id: int = Field(ge=1)
    question_crop_path: str
    question_crop_sha256: str
    question_crop_width: int = Field(gt=0)
    question_crop_height: int = Field(gt=0)
    proposals: list[FigureProposal]

    _validate_question_hash = field_validator("question_crop_sha256")(
        _valid_sha256
    )
    _validate_question_path = field_validator("question_crop_path")(
        _valid_source_reference
    )


class FigureAsset(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    pipeline_version: Literal["figure-b1-v1"] = "figure-b1-v1"
    document_id: str
    asset_id: str
    parent_question_id: str
    asset_type: Literal["figure"] = "figure"
    figure_type: Literal["unknown"] = "unknown"
    source: AssetSource
    provenance: AssetProvenance
    visible_labels: list[object] = Field(default_factory=list, max_length=0)
    description: None = None
    entities: list[object] = Field(default_factory=list, max_length=0)
    relations: list[object] = Field(default_factory=list, max_length=0)
    validation: AssetValidation = Field(default_factory=AssetValidation)

    @model_validator(mode="after")
    def validate_identity(self) -> "FigureAsset":
        if not _DOCUMENT_ID_RE.fullmatch(self.document_id):
            raise ValueError("invalid document_id")
        if not _QUESTION_ID_RE.fullmatch(self.parent_question_id):
            raise ValueError("invalid parent_question_id")
        if not _ASSET_ID_RE.fullmatch(self.asset_id):
            raise ValueError("invalid asset_id")
        if not self.parent_question_id.startswith(self.document_id + "-q"):
            raise ValueError("question ID does not belong to document")
        if not self.asset_id.startswith(self.parent_question_id + "-fig"):
            raise ValueError("asset ID does not belong to parent question")
        return self
```

Create `2_生產線/src/figure_pipeline/__init__.py`:

```python
from .models import FigureAsset, FigureProposal, ProposalBundle

__all__ = ["FigureAsset", "FigureProposal", "ProposalBundle"]
```

Also create empty package markers:

```text
2_生產線/tests/figure_pipeline/__init__.py
```

- [ ] **Step 5: Run the tests and verify GREEN**

Run the Step 3 command again.

Expected: `6 passed`.

---

### Task 2: Load question metadata and generate MinerU proposals

**Files:**

- Create: `2_生產線/src/figure_pipeline/source.py`
- Create: `2_生產線/src/figure_pipeline/detectors/__init__.py`
- Create: `2_生產線/src/figure_pipeline/detectors/base.py`
- Create: `2_生產線/src/figure_pipeline/detectors/mineru.py`
- Create: `2_生產線/tests/figure_pipeline/test_source_and_mineru.py`

- [ ] **Step 1: Write failing source and detector tests**

Create `2_生產線/tests/figure_pipeline/test_source_and_mineru.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
uv run python -m pytest 2_生產線/tests/figure_pipeline/test_source_and_mineru.py -q `
  -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b1-source
```

Expected: collection fails because `figure_pipeline.source` and detector
modules do not exist.

- [ ] **Step 3: Implement the Stage1 source loader**

Create `2_生產線/src/figure_pipeline/source.py`:

```python
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
```

- [ ] **Step 4: Implement the detector protocol and MinerU adapter**

Create `2_生產線/src/figure_pipeline/detectors/base.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from figure_pipeline.models import FigureProposal


class FigureDetector(Protocol):
    def detect(self, question_crop: Path, *, page: int) -> list[FigureProposal]:
        ...
```

Create `2_生產線/src/figure_pipeline/detectors/mineru.py`:

```python
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image

from figure_pipeline.models import FigureProposal
from ocr_pipeline.engines.mineru_layout import MineruLayoutEngine
from ocr_pipeline.models import BlockType


class MineruFigureDetector:
    name = "mineru_pp_doclayout_v2"

    def __init__(self, *, engine: Any | None = None, device: str = "cuda") -> None:
        self.engine = engine or MineruLayoutEngine(device=device)

    def detect(self, question_crop: Path, *, page: int) -> list[FigureProposal]:
        with Image.open(question_crop) as image:
            width, height = image.size

        proposals: list[FigureProposal] = []
        for block in self.engine.analyze(question_crop, page=page):
            if block.block_type is not BlockType.FIGURE:
                continue
            bbox = (
                math.floor(block.bbox.x1),
                math.floor(block.bbox.y1),
                math.ceil(block.bbox.x2),
                math.ceil(block.bbox.y2),
            )
            x1, y1, x2, y2 = bbox
            if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
                continue
            if x2 <= x1 or y2 <= y1:
                continue
            proposals.append(
                FigureProposal(
                    bbox=bbox,
                    label=str(block.meta.get("label") or "figure"),
                    detector=self.name,
                )
            )
        return proposals
```

Create both detector `__init__.py` files with explicit exports:

```python
from .mineru import MineruFigureDetector

__all__ = ["MineruFigureDetector"]
```

- [ ] **Step 5: Run the tests and verify GREEN**

Run the Step 2 command again.

Expected: `2 passed`.

---

### Task 3: Write proposal JSON and overlay safely

**Files:**

- Create: `2_生產線/src/figure_pipeline/proposal.py`
- Create: `2_生產線/tests/figure_pipeline/test_proposal.py`

- [ ] **Step 1: Write failing proposal tests**

Create `2_生產線/tests/figure_pipeline/test_proposal.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from figure_pipeline.models import FigureProposal
from figure_pipeline.proposal import create_proposal_bundle
from figure_pipeline.source import QuestionSource


class FakeDetector:
    def detect(self, question_crop: Path, *, page: int) -> list[FigureProposal]:
        return [
            FigureProposal(
                bbox=(10, 20, 80, 70),
                label="image",
                detector="fake",
                confidence=0.9,
            )
        ]


def source_for(crop: Path) -> QuestionSource:
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


def test_create_proposal_bundle_writes_json_and_overlay(tmp_path: Path) -> None:
    crop = tmp_path / "question.png"
    Image.new("RGB", (100, 80), "white").save(crop)
    out = tmp_path / "proposal"

    bundle = create_proposal_bundle(source_for(crop), FakeDetector(), out)

    assert bundle.proposals[0].bbox == (10, 20, 80, 70)
    assert (out / "proposal.json").is_file()
    assert (out / "proposal_overlay.png").is_file()
    saved = json.loads((out / "proposal.json").read_text(encoding="utf-8"))
    assert saved["question_crop_sha256"] == bundle.question_crop_sha256


def test_create_proposal_bundle_refuses_existing_destination(
    tmp_path: Path,
) -> None:
    crop = tmp_path / "question.png"
    Image.new("RGB", (100, 80), "white").save(crop)
    out = tmp_path / "proposal"
    out.mkdir()

    with pytest.raises(FileExistsError):
        create_proposal_bundle(source_for(crop), FakeDetector(), out)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
uv run python -m pytest 2_生產線/tests/figure_pipeline/test_proposal.py -q `
  -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b1-proposal
```

Expected: collection fails because `figure_pipeline.proposal` does not exist.

- [ ] **Step 3: Implement proposal generation**

Create `2_生產線/src/figure_pipeline/proposal.py`:

```python
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
        question_crop_path=source.crop_path.as_posix(),
        question_crop_sha256=sha256_file(source.crop_path),
        question_crop_width=image.width,
        question_crop_height=image.height,
        proposals=proposals,
    )

    stage = destination.parent / f".{destination.name}.staging-{uuid.uuid4().hex}"
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
        return bundle
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run the Step 2 command again.

Expected: `2 passed`.

---

### Task 4: Preserve confirmed and manual assets atomically

**Files:**

- Create: `2_生產線/src/figure_pipeline/preserve.py`
- Create: `2_生產線/tests/figure_pipeline/test_preserve.py`

- [ ] **Step 1: Write failing preservation tests**

Create `2_生產線/tests/figure_pipeline/test_preserve.py`:

```python
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
        question_crop_path=source.crop_path.as_posix(),
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
    saved = json.loads((out / "figure_asset.json").read_text(encoding="utf-8"))
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
uv run python -m pytest 2_生產線/tests/figure_pipeline/test_preserve.py -q `
  -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b1-preserve
```

Expected: collection fails because `figure_pipeline.preserve` does not exist.

- [ ] **Step 3: Implement atomic preservation**

Create `2_生產線/src/figure_pipeline/preserve.py`:

```python
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
        raise ValueError("proposal bundle and candidate index must be supplied together")

    with Image.open(source.crop_path) as opened:
        question_image = opened.convert("RGB")
        question_image.load()
    bbox = _validate_bbox(
        bbox,
        width=question_image.width,
        height=question_image.height,
    )

    stage = destination.parent / f".{destination.name}.staging-{uuid.uuid4().hex}"
    stage.mkdir(parents=True)
    try:
        question_path = stage / "question.png"
        shutil.copy2(source.crop_path, question_path)
        if sha256_file(question_path) != sha256_file(source.crop_path):
            raise RuntimeError("question crop hash mismatch")

        asset_dir = stage / "assets"
        asset_dir.mkdir()
        figure_path = asset_dir / f"q{source.question_id:03d}_fig01.png"
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
                question_crop_sha256=sha256_file(question_path),
                question_bbox=source.question_bbox,
                crop_path=f"assets/q{source.question_id:03d}_fig01.png",
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
        if sha256_file(stage / round_trip.source.crop_path) != round_trip.source.sha256:
            raise RuntimeError("figure crop hash mismatch")
        stage.rename(destination)
        return round_trip
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run the Step 2 command again.

Expected: `7 passed`.

- [ ] **Step 5: Run all Figure unit tests**

Run:

```powershell
uv run python -m pytest 2_生產線/tests/figure_pipeline -q -p no:cacheprovider `
  --basetemp .pytest-tmp-local/figure-b1-all
```

Expected: `17 passed`, zero failures.

---

### Task 5: Add CLI, package metadata and real Q18 acceptance

**Files:**

- Create: `2_生產線/src/figure_pipeline/cli.py`
- Create: `2_生產線/_script/phase_b1_figure_asset.py`
- Create: `2_生產線/tests/figure_pipeline/test_cli.py`
- Modify: `pyproject.toml`
- Create: `3.分析結果/docs/figure_pipeline/progress.md`
- Generate: `3.分析結果/output/figure_pipeline/2015p2/q018-proposal/**`
- Generate after human confirmation:
  `3.分析結果/output/figure_pipeline/2015p2/q018/**`

- [ ] **Step 1: Write failing CLI tests**

Create `2_生產線/tests/figure_pipeline/test_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from figure_pipeline.cli import main
from figure_pipeline.models import FigureProposal


class FakeDetector:
    def detect(self, question_crop: Path, *, page: int) -> list[FigureProposal]:
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
uv run python -m pytest 2_生產線/tests/figure_pipeline/test_cli.py -q `
  -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b1-cli
```

Expected: collection fails because `figure_pipeline.cli` does not exist.

- [ ] **Step 3: Implement the CLI**

Create `2_生產線/src/figure_pipeline/cli.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .detectors.base import FigureDetector
from .detectors.mineru import MineruFigureDetector
from .models import ProposalBundle
from .preserve import preserve_asset
from .proposal import create_proposal_bundle
from .source import load_question_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Figure Phase B1 preservation")
    commands = parser.add_subparsers(dest="command", required=True)

    propose = commands.add_parser("propose")
    propose.add_argument("--layout", type=Path, required=True)
    propose.add_argument("--question-id", type=int, required=True)
    propose.add_argument("--out", type=Path, required=True)

    preserve = commands.add_parser("preserve")
    preserve.add_argument("--layout", type=Path, required=True)
    preserve.add_argument("--question-id", type=int, required=True)
    preserve.add_argument("--proposal", type=Path)
    preserve.add_argument("--candidate", type=int)
    preserve.add_argument("--manual-bbox", type=int, nargs=4)
    preserve.add_argument("--out", type=Path, required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    detector: FigureDetector | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    source = load_question_source(args.layout, question_id=args.question_id)

    if args.command == "propose":
        create_proposal_bundle(
            source,
            detector or MineruFigureDetector(),
            args.out,
        )
        return 0

    if args.manual_bbox is not None:
        if args.proposal is not None or args.candidate is not None:
            raise SystemExit(
                "--manual-bbox cannot be combined with --proposal/--candidate"
            )
        preserve_asset(
            source=source,
            destination=args.out,
            manual_bbox=tuple(args.manual_bbox),
        )
        return 0

    if args.proposal is None or args.candidate is None:
        raise SystemExit(
            "preserve requires --proposal and --candidate, or --manual-bbox"
        )
    bundle = ProposalBundle.model_validate_json(
        args.proposal.read_text(encoding="utf-8")
    )
    preserve_asset(
        source=source,
        destination=args.out,
        proposal_bundle=bundle,
        candidate_index=args.candidate,
    )
    return 0
```

Create `2_生產線/_script/phase_b1_figure_asset.py`:

```python
from __future__ import annotations

from figure_pipeline.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add the package to wheel configuration**

Change `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["2_生產線/src/ocr_pipeline", "2_生產線/src/figure_pipeline"]
```

- [ ] **Step 5: Run CLI and full Figure tests**

Run:

```powershell
uv run python -m pytest 2_生產線/tests/figure_pipeline -q -p no:cacheprovider `
  --basetemp .pytest-tmp-local/figure-b1-final
uv run ruff check 2_生產線/src/figure_pipeline 2_生產線/_script/phase_b1_figure_asset.py `
  2_生產線/tests/figure_pipeline
uv run python -m py_compile 2_生產線/_script/phase_b1_figure_asset.py `
  2_生產線/src/figure_pipeline/models.py 2_生產線/src/figure_pipeline/source.py `
  2_生產線/src/figure_pipeline/proposal.py 2_生產線/src/figure_pipeline/preserve.py `
  2_生產線/src/figure_pipeline/cli.py 2_生產線/src/figure_pipeline/detectors/base.py `
  2_生產線/src/figure_pipeline/detectors/mineru.py
```

Expected:

- pytest: `19 passed`, zero failures;
- Ruff: exit 0 with no diagnostics;
- py_compile: exit 0 with no output.

- [ ] **Step 6: Verify Track A files were not modified**

Run:

```powershell
git status --short --untracked-files=all -- 2_生產線/src/ocr_pipeline 2_生產線/tests/test_mcq_*.py
```

Expected: no new modification attributable to Phase B1. Because the parent
repository lacks a usable baseline, also compare mtimes and file hashes
captured immediately before implementation.

- [ ] **Step 7: Run the real MinerU proposal on Q18**

Preflight:

```powershell
Test-Path 1_收集資料/data/pdf_pages/2015p2/crops/p006_q018.png
Test-Path 3.分析結果/output/figure_pipeline/2015p2/q018-proposal
```

Expected: first command `True`; second command `False`.

Run in the foreground:

```powershell
uv run python 2_生產線/_script/phase_b1_figure_asset.py propose `
  --layout 1_收集資料/data/pdf_pages/2015p2/layout.json `
  --question-id 18 `
  --out 3.分析結果/output/figure_pipeline/2015p2/q018-proposal
```

Expected:

- process exits 0;
- `proposal.json` exists;
- `proposal_overlay.png` exists;
- no final `q018/figure_asset.json` exists yet.

If MinerU fails to load its dependency or model, or inference itself fails,
record the exact error once and do not repeat the same command. Confirm that
the atomic proposal destination was not published, then continue at the manual
bbox review branch in Step 8.

- [ ] **Step 8: Human-review the proposal overlay**

Open or render:

```text
3.分析結果/output/figure_pipeline/2015p2/q018-proposal/proposal_overlay.png
```

Report every proposal index and bbox. Ask the user to approve one candidate.
Do not preserve an asset before explicit candidate approval.

If there are no valid proposals, or the user rejects every proposal, inspect
the Q18 question crop and obtain an explicit manual bbox in
`question_crop_pixels`.

- [ ] **Step 9: Publish the final sample with the approved boundary**

For an approved candidate index of `0`, run:

```powershell
uv run python 2_生產線/_script/phase_b1_figure_asset.py preserve `
  --layout 1_收集資料/data/pdf_pages/2015p2/layout.json `
  --question-id 18 `
  --proposal 3.分析結果/output/figure_pipeline/2015p2/q018-proposal/proposal.json `
  --candidate 0 `
  --out 3.分析結果/output/figure_pipeline/2015p2/q018
```

If the user approves a different candidate, replace only the final integer
after `--candidate` with that exact approved index.

For manual fallback, use the same `preserve` command, omit `--proposal` and
`--candidate`, and append `--manual-bbox` followed verbatim by the four
user-approved `question_crop_pixels` integers. The bbox is runtime review data,
so the plan intentionally does not predetermine it.

- [ ] **Step 10: Verify the final artifact and record Figure progress**

Run a read-only verification that:

1. parses `figure_asset.json` with `FigureAsset`;
2. resolves `question_crop_path` and `crop_path` relative to the JSON;
3. recomputes both SHA-256 values;
4. checks `parent_question_id == "hk-dse-2015-math-p2-q018"`;
5. checks `validation == {"status": "pending", "reviewed": false}`.

Use:

```powershell
uv run python -c "from pathlib import Path; from figure_pipeline.models import FigureAsset; from figure_pipeline.proposal import sha256_file; p=Path('3.分析結果/output/figure_pipeline/2015p2/q018/figure_asset.json'); a=FigureAsset.model_validate_json(p.read_text(encoding='utf-8')); root=p.parent; assert sha256_file(root/a.source.question_crop_path)==a.source.question_crop_sha256; assert sha256_file(root/a.source.crop_path)==a.source.sha256; assert a.parent_question_id=='hk-dse-2015-math-p2-q018'; assert a.validation.status=='pending' and a.validation.reviewed is False; print(a.asset_id, a.source.bbox, a.source.sha256)"
```

Expected: exit 0 and one line containing the stable asset ID, accepted bbox and
64-character SHA-256.

Create `3.分析結果/docs/figure_pipeline/progress.md` with:

```markdown
# Figure Pipeline Progress

## 2026-07-31 — Phase B1 Q18 acceptance

- Design:
  `3.分析結果/docs/superpowers/specs/2026-07-31-figure-phase-b1-asset-preservation-design.md`
- Plan:
  `3.分析結果/docs/superpowers/plans/2026-07-31-figure-phase-b1-asset-preservation.md`
- Sample: `hk-dse-2015-math-p2-q018-fig01`
- Boundary source: record `mineru_confirmed` plus candidate index, or `manual`.
- Focused pytest: record exact passed count.
- Ruff: record exit status.
- Artifact verification: record accepted bbox and matching SHA-256.
- Track A files modified: none.
- VLM / embedding / Qdrant operations: none.
```

Replace only the evidence phrases with the exact observed results. Do not
record success before the verification commands pass.

---

## Final verification checklist

- [ ] Every new production function was preceded by an observed failing test.
- [ ] All `2_生產線/tests/figure_pipeline` tests pass.
- [ ] Ruff and py_compile pass.
- [ ] Q18 MinerU proposals were shown to the user.
- [ ] The accepted candidate or manual bbox has explicit user approval.
- [ ] Final question and figure crop hashes match `figure_asset.json`.
- [ ] Stable parent/asset linkage is correct.
- [ ] Track A source and output contracts are unchanged.
- [ ] No VLM, embedding or Qdrant operation occurred.
- [ ] No commit, stage, push or PR was performed.
