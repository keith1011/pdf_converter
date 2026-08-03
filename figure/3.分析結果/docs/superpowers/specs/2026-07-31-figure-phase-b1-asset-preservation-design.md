# Figure Phase B1 Asset Preservation Design

**Date:** 2026-07-31  
**Track:** Figure / Table Track B  
**Status:** Approved design; implementation not started  
**Acceptance sample:** HKDSE 2015 Mathematics Compulsory Part Paper 2, Question 18

## 1. Goal

Build the first traceable Figure pipeline milestone without changing the copied
Track A OCR pipeline.

For 2015 Paper 2 Question 18, the milestone must preserve:

1. the original question crop;
2. a human-confirmed figure crop;
3. the figure bbox and its coordinate space;
4. stable question and asset IDs;
5. a SHA-256 digest of the saved figure crop;
6. a validated `FigureAsset` JSON that can locate the crop again.

Phase B1 does not analyze or describe the figure.

## 2. Scope

### In scope

- A new, isolated `2_生產線/src/figure_pipeline/` package.
- `FigureAsset` and supporting Phase B1 models.
- MinerU figure-region proposals on a question crop.
- Explicit human acceptance of a MinerU proposal.
- Manual bbox fallback when MinerU produces no valid proposal or the human
  reviewer rejects every proposal.
- Deterministic cropping, hashing, JSON serialization and no-overwrite safety.
- A sample artifact bundle for 2015 Paper 2 Question 18.
- Focused unit tests and one acceptance verification using the real sample.

### Out of scope

- Figure classification beyond the placeholder `figure_type: "unknown"`.
- Caption generation or visible-label OCR.
- Geometry, graph, chart or table understanding.
- Embeddings or Qdrant operations.
- Answer inference.
- Changes to `2_生產線/src/ocr_pipeline/`, MCQ schemas, renderers or Track A output.
- Automatic acceptance of detector output.

## 3. Source data

The acceptance sample already exists:

```text
PDF:
  1_收集資料/data/sources/2015p2.pdf

Layout:
  1_收集資料/data/pdf_pages/2015p2/layout.json

Question crop:
  1_收集資料/data/pdf_pages/2015p2/crops/p006_q018.png

Layout metadata:
  page = 6
  question_id = 18
  question_bbox = [162, 1377, 1587, 2179]
  question_bbox_space = "page_pixels"
```

The question crop contains a visible geometry diagram. It is not itself a
Figure asset because it also contains the stem and answer choices.

## 4. Stable identity

The first sample uses:

```text
document_id:
  hk-dse-2015-math-p2

parent_question_id:
  hk-dse-2015-math-p2-q018

asset_id:
  hk-dse-2015-math-p2-q018-fig01
```

IDs come from the document and Stage1 question identity. They must not depend
on array position, directory listing order, detector order or VLM output.

The asset ordinal is explicit. Later support for multiple assets may allocate
`fig02`, `fig03`, and so on, but Phase B1 does not implement automatic ordinal
assignment.

## 5. Architecture

### 5.1 `2_生產線/src/figure_pipeline/models.py`

Define Pydantic v2 models for:

- `AssetSource`
- `AssetValidation`
- `AssetProvenance`
- `FigureAsset`

The models validate:

- schema version;
- stable ID formats and parent/child linkage;
- positive page number;
- four-integer, non-empty bbox;
- declared bbox coordinate space;
- lowercase 64-character SHA-256;
- fixed Phase B1 defaults;
- pending and unreviewed semantic validation.

### 5.2 `2_生產線/src/figure_pipeline/detectors/base.py`

Define a small detector interface and a `FigureProposal` model. A proposal
contains:

- bbox;
- bbox coordinate space;
- raw detector label;
- detector name;
- optional confidence when the detector provides it.

Detector output is a proposal, never an accepted asset boundary.

### 5.3 `2_生產線/src/figure_pipeline/detectors/mineru.py`

Wrap the copied repository's existing `MineruLayoutEngine` without modifying
it.

The adapter:

1. runs MinerU on the question crop;
2. keeps only blocks mapped to `BlockType.FIGURE`;
3. validates each bbox against question-crop dimensions;
4. emits `FigureProposal` objects in `question_crop_pixels`;
5. preserves the raw MinerU label from block metadata.

The adapter must not select a proposal automatically.

### 5.4 `2_生產線/src/figure_pipeline/preserve.py`

Provide the pure Phase B1 preservation workflow:

- validate source metadata and selected bbox;
- copy the original question crop into a staging bundle;
- crop the figure from question-crop pixels;
- save the final figure PNG;
- calculate and re-check SHA-256;
- construct and validate `FigureAsset`;
- write deterministic UTF-8 JSON;
- publish the completed bundle by directory rename.

The workflow accepts exactly one of:

- a human-confirmed MinerU proposal; or
- an explicit manual bbox.

### 5.5 `2_生產線/_script/phase_b1_figure_asset.py`

Provide a thin CLI with two operations.

Proposal operation:

```powershell
uv run python 2_生產線/_script/phase_b1_figure_asset.py propose `
  --layout 1_收集資料/data/pdf_pages/2015p2/layout.json `
  --question-id 18 `
  --out 3.分析結果/output/figure_pipeline/2015p2/q018-proposal
```

It writes proposal metadata and a visual overlay, but no final Figure asset.
The proposal metadata includes the question ID, question-crop path,
question-crop dimensions and question-crop SHA-256. Acceptance verifies these
fields before using a candidate.

Acceptance operation using MinerU:

```powershell
uv run python 2_生產線/_script/phase_b1_figure_asset.py preserve `
  --layout 1_收集資料/data/pdf_pages/2015p2/layout.json `
  --question-id 18 `
  --proposal 3.分析結果/output/figure_pipeline/2015p2/q018-proposal/proposal.json `
  --candidate 0 `
  --out 3.分析結果/output/figure_pipeline/2015p2/q018
```

Manual fallback:

```powershell
uv run python 2_生產線/_script/phase_b1_figure_asset.py preserve `
  --layout 1_收集資料/data/pdf_pages/2015p2/layout.json `
  --question-id 18 `
  --manual-bbox X1 Y1 X2 Y2 `
  --out 3.分析結果/output/figure_pipeline/2015p2/q018
```

`X1 Y1 X2 Y2` are required integer coordinates in
`question_crop_pixels`; they are command syntax variables, not unresolved
design values.

The CLI delegates validation and file operations to the package. It contains
no schema or cropping logic of its own.

## 6. Coordinate contract

The layout artifact uses page-pixel coordinates for the question bbox.

MinerU runs on the question crop. Every accepted figure bbox is converted to
and stored as:

```text
bbox_space = "question_crop_pixels"
bbox = [x1, y1, x2, y2]
origin = top-left of the saved question crop
```

The `FigureAsset` also stores the question bbox and its page-pixel coordinate
space. This preserves the path back to the page while preventing accidental
mixing of page and crop coordinates.

MinerU output formats may expose pixel or normalized coordinates depending on
the API and output file. The new adapter owns that conversion. Downstream
preservation code receives only validated question-crop pixel coordinates.

## 7. FigureAsset schema

The Phase B1 JSON has this shape. The example bbox `[1, 1, 2, 2]` and
all-zero digest demonstrate valid field formats only; the acceptance artifact
must contain the confirmed Q18 bbox and the digest recalculated from its saved
crop.

```json
{
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
    "original_question_crop_path": "1_收集資料/data/pdf_pages/2015p2/crops/p006_q018.png",
    "question_crop_path": "question.png",
    "question_crop_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "question_bbox": [162, 1377, 1587, 2179],
    "question_bbox_space": "page_pixels",
    "crop_path": "assets/q018_fig01.png",
    "bbox": [1, 1, 2, 2],
    "bbox_space": "question_crop_pixels",
    "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "provenance": {
    "method": "mineru_confirmed",
    "detector": "mineru_pp_doclayout_v2",
    "detector_label": "image",
    "candidate_index": 0
  },
  "visible_labels": [],
  "description": null,
  "entities": [],
  "relations": [],
  "validation": {
    "status": "pending",
    "reviewed": false
  }
}
```

For manual fallback:

```json
{
  "method": "manual",
  "detector": null,
  "detector_label": null,
  "candidate_index": null
}
```

Human confirmation approves only the crop boundary. Semantic validation
remains pending and unreviewed.

## 8. Artifact bundle

Proposal bundle:

```text
3.分析結果/output/figure_pipeline/2015p2/q018-proposal/
├── proposal.json
└── proposal_overlay.png
```

Final bundle:

```text
3.分析結果/output/figure_pipeline/2015p2/q018/
├── question.png
├── assets/
│   └── q018_fig01.png
└── figure_asset.json
```

`figure_asset.json` uses paths relative to its bundle. A consumer resolves
them against the directory containing the JSON file.

## 9. Proposal and fallback behavior

### MinerU proposal path

- Zero valid proposals: proposal output records an empty list; final
  preservation stops and directs the caller to manual bbox mode.
- One valid proposal: it is displayed but still requires explicit
  `--candidate 0`.
- Multiple valid proposals: all are displayed; the caller must select one
  candidate.
- If the human reviewer rejects every valid proposal, preservation uses the
  explicit manual bbox path instead.
- Candidate indices are proposal-file data, not stable asset identity.

### Manual fallback path

Manual mode is allowed only when an explicit bbox is supplied after MinerU
returns no valid proposal or the human reviewer rejects all proposals. The
asset records `provenance.method: "manual"`.

Manual mode uses the same validation, cropping, hashing, JSON and publication
logic as the MinerU-confirmed path.

## 10. Safety and failure handling

- Reject empty, inverted, non-integer or out-of-bounds bbox values.
- Refuse to overwrite an existing proposal or final output directory.
- Refuse candidate selection when the proposal metadata does not match the
  requested question crop, question ID, crop dimensions or crop SHA-256.
- Write a staging bundle in the destination parent directory.
- Verify that the copied question crop has the same SHA-256 as the original.
- Recalculate the saved figure crop's SHA-256 before publication.
- Validate the serialized JSON by reading it back into `FigureAsset`.
- Rename the staging directory to the final destination only after every check
  passes.
- A failed operation must not leave a final output bundle.
- Temporary cleanup must target only the explicitly created staging directory.

## 11. Testing strategy

Follow Red-Green-Refactor. No production behavior is added before its failing
test is observed.

Focused tests:

1. `test_figure_asset_models.py`
   - valid schema;
   - stable ID parent linkage;
   - invalid hash, bbox and fixed-field rejection.
2. `test_mineru_figure_detector.py`
   - filters non-figure blocks;
   - preserves raw label;
   - converts and validates bbox coordinates;
   - never auto-selects.
3. `test_asset_preservation.py`
   - confirmed proposal produces expected crop and JSON;
   - saved crop hash matches JSON;
   - copied question crop hash matches the original;
   - relative paths resolve from the asset JSON.
4. `test_asset_preservation_manual.py`
   - manual fallback produces the same schema;
   - provenance records the manual method.
5. `test_asset_preservation_safety.py`
   - invalid and out-of-bounds bbox;
   - candidate/question mismatch;
   - existing destination;
   - failed workflow leaves no final bundle.

Unit tests use a small fake detector only at the detector boundary. Cropping,
hashing, serialization and filesystem behavior use real code and real
temporary images.

The acceptance smoke uses the real 2015 Q18 crop and MinerU model. It is
separate from the default unit suite because model availability and GPU
runtime are environment-dependent.

## 12. Acceptance criteria

Phase B1 is complete only when:

1. MinerU proposals for the Q18 question crop have been inspected.
2. A proposal is explicitly confirmed, or a manual bbox is supplied after
   MinerU has no valid proposal or the reviewer rejects every proposal.
3. The final bundle contains the original question crop, figure crop and
   validated `figure_asset.json`.
4. The figure crop path resolves and its SHA-256 matches the JSON.
5. `asset_id` is linked to the expected `parent_question_id`.
6. The bbox coordinate spaces are explicit and internally consistent.
7. Focused tests pass with no failures.
8. Existing Track A source and output contracts remain unchanged.
9. No VLM, embedding or Qdrant operation occurs.

## 13. Delivery constraints

- Python 3.12 and the existing `uv` environment.
- No concurrent GPU pipelines.
- No modification of copied Track A production code.
- No overwrite of existing artifacts.
- No secrets or credentials.
- No commit, stage, push or PR unless the user explicitly asks.
