# Figure Phase B2 Qwen Semantic Classification Design

**Date:** 2026-08-02  
**Track:** Figure / Table Track B  
**Status:** Approved design; implementation pending  
**Depends on:** Phase B1 asset preservation

## 1. Goal

Add a traceable Phase B2 classification stage for preserved Figure assets.
Qwen3-VL-8B-Instruct in the existing local 4-bit runtime is the semantic
classifier. It must propose a controlled `visual_family` and `subtype`, retain
observable evidence and model provenance, and never silently turn an unreviewed
proposal into an accepted semantic label.

The first acceptance sample remains the preserved HKDSE 2015 Mathematics
Paper 2 Question 18 figure. Phase B2 must leave the Phase B1 crop, bbox,
provenance and hashes unchanged.

## 2. Scope

### In scope

- A strict B2 classification schema layered on the existing `FigureAsset`.
- A local Qwen3-VL classifier adapter that reuses the existing VLM client and
  model-loading path.
- A versioned classification prompt that requests exactly one JSON object.
- Pydantic validation for the model response and the controlled taxonomy.
- Separate `proposed` and `reviewed` classification records in the B2 asset
  JSON.
- Sequential GPU inference with one model client per batch.
- Atomic, no-overwrite B2 artifact publication.
- Recorded-response tests that do not require a GPU in CI.
- An explicit CLI path for generating proposals and recording human review.

### Out of scope

- Replacing MinerU layout detection or changing the Phase B1 bbox contract.
- Visible-label OCR, captioning, entity extraction or relation extraction;
  those remain B3/B4 work.
- Automatic answer solving or question-text classification.
- PaddleOCR integration in the B2 classifier.
- Fine-tuning Qwen, training a new classifier, embeddings or Qdrant ingest.
- A browser UI; review remains a local, auditable CLI/data operation.

## 3. Source and identity contract

The classifier consumes a published B1 asset bundle, not a PDF page and not a
raw MinerU response. The canonical model input is:

```text
3.分析結果/output/figure_pipeline/<document>/q<question>/assets/q<question>_figNN.png
```

The runner verifies the asset JSON, the crop path and the crop SHA-256 before
calling Qwen. `asset_id`, `parent_question_id`, page and bbox metadata are
carried into the output for traceability but are not supplied as semantic
clues to the model. The default prompt is crop-only so classification cannot
become a guess based on question text or answer choices.

B1 artifacts remain readable and immutable. B2 publishes a new versioned
asset JSON rather than overwriting `figure_asset.json`.

## 4. Architecture

### 4.1 Classification models

Add strict models beside the existing B1 models:

- `VisualFamily`: `geometry`, `coordinate_graph`, `function_graph`,
  `statistical_chart`, `table`, `physical_diagram`, `illustration` or
  `unknown`.
- `ClassificationProposal`: primary family, controlled subtype, up to three
  secondary tags, confidence, observable evidence, model metadata and review
  routing state.
- `ReviewedClassification`: the human-approved or human-corrected primary
  family, subtype, secondary tags, reviewer status and source proposal ID.
- `FigureClassification`: `proposed`, `reviewed`, parser status and optional
  raw-response reference.

`secondary_tags` use the same non-`unknown` `VisualFamily` values, are unique,
and cannot repeat the primary family. A mixed figure therefore has one stable
primary leaf and additional semantic tags instead of multiple competing
primary labels.

### 4.2 Controlled subtype vocabulary

The first vocabulary is intentionally small and has an explicit `other`
fallback. Qwen must not invent a new subtype in its response.

| Visual family | Initial subtypes |
| --- | --- |
| `geometry` | `triangle`, `quadrilateral`, `circle`, `polygon`, `solid`, `angle`, `transformation`, `other` |
| `coordinate_graph` | `point_plot`, `line_segment`, `locus`, `vector`, `other` |
| `function_graph` | `linear`, `quadratic`, `polynomial`, `piecewise`, `trigonometric`, `exponential`, `other` |
| `statistical_chart` | `bar`, `line`, `pie`, `scatter`, `box`, `histogram`, `other` |
| `table` | `data_table`, `frequency_table`, `value_table`, `other` |
| `physical_diagram` | `flowchart`, `circuit`, `mechanical`, `engineering`, `chemistry`, `other` |
| `illustration` | `map`, `photo`, `decorative`, `other` |
| `unknown` | `unclassified` |

The validator enforces family/subtype compatibility. `unknown` always uses
`unclassified`; all other families require one subtype from their row.

### 4.3 Qwen adapter and prompt boundary

The adapter reuses `build_vlm_client` and the local model configured for the
existing Qwen3-VL 4-bit OCR path. It adds a separate classification prompt;
the OCR prompts and their parsers are not reused.

The prompt instructs Qwen to:

1. inspect only the supplied figure crop;
2. choose exactly one allowed `visual_family` and compatible `subtype`;
3. use `secondary_tags` only when a second visual family is visibly present;
4. choose `unknown` when the crop is ambiguous or insufficient;
5. provide short, observable evidence rather than hidden reasoning;
6. return one JSON object with no Markdown fences, prose, answer choice or
   mathematical solution.

The response parser accepts one JSON object only. It rejects unknown keys,
invalid enums, incompatible subtype values, non-numeric confidence and
evidence that is not a short string list.

## 5. B2 asset schema

B2 uses `schema_version: "1.1"` and `pipeline_version: "figure-b2-v1"`.
All B1 source and provenance fields remain unchanged. The additive shape is:

```json
{
  "schema_version": "1.1",
  "pipeline_version": "figure-b2-v1",
  "figure_type": "unknown",
  "classification": {
    "proposed": {
      "visual_family": "geometry",
      "subtype": "triangle",
      "secondary_tags": [],
      "confidence": 0.91,
      "evidence": [
        "Visible straight edges form a triangle",
        "Angle markers are present"
      ],
      "needs_review": true,
      "model_id": "Qwen/Qwen3-VL-8B-Instruct",
      "quantization": "4-bit",
      "prompt_version": "figure-b2-v1"
    },
    "reviewed": null,
    "status": "pending"
  }
}
```

`figure_type` stays `unknown` until `reviewed` is approved. Once a reviewer
approves or corrects the proposal, `figure_type` is derived from the reviewed
primary family for backward-compatible consumers. The raw model response is
stored as a separate local artifact only when needed for audit or parser
failure; its path and SHA-256 may be recorded in `classification`.

## 6. Review and state transitions

Every initial proposal requires human review. Model confidence is a routing
hint, not an auto-approval rule. The allowed transitions are:

```text
pending → approved
pending → corrected
pending → rejected
pending → failed
```

- `approved`: the reviewer accepts the proposal unchanged.
- `corrected`: the reviewer supplies a valid family/subtype and may edit tags.
- `rejected`: the asset is not a supported Figure classification and remains
  semantically unresolved.
- `failed`: Qwen or validation failed before a usable proposal existed.

Rejected, failed and `unknown` results remain available for later B3/B4 review;
the pipeline must not guess a replacement label.

## 7. Data flow and CLI boundary

The implementation will expose a thin CLI with separate proposal and review
operations. The exact module names may follow the existing `phase_b1` CLI
pattern, but the boundary is fixed:

```powershell
uv run python 2_生產線/_script/phase_b2_figure_classify.py propose `
  --asset 3.分析結果/output/figure_pipeline/2015p2/q018 `
  --out 3.分析結果/output/figure_pipeline/2015p2/q018-b2
```

The proposal operation validates the B1 bundle, loads one Qwen client, runs
sequential classification, validates the response, writes the proposed B2
asset and publishes it by directory rename. It must fail without partial
output when the source asset, crop hash or model cannot be loaded.

The review operation accepts an explicit B2 asset plus a reviewer decision and
validates that decision against the same taxonomy before publishing a reviewed
asset. It must never edit the B1 directory in place.

## 8. Error handling and reproducibility

- Missing source, invalid B1 JSON or crop hash mismatch: fail before inference.
- Model load or inference error: publish no B2 asset; return a non-zero CLI exit.
- Non-JSON, fenced or schema-invalid Qwen output: write a failed classification
  artifact with the raw response reference and leave `figure_type` unknown.
- Any filesystem publication failure: remove only the operation's staging
  directory and preserve all existing artifacts.
- Prompt version, model ID, quantization, source crop SHA-256 and parser status
  are recorded for every successful or failed proposal.
- GPU execution is sequential; the runner must release the Qwen client before
  normal process exit.

## 9. Testing and acceptance

### Unit tests

- Enum and family/subtype compatibility validation.
- Mixed-figure primary plus secondary-tag validation.
- Strict JSON parsing, fenced-output rejection and unknown-key rejection.
- Invalid confidence/evidence handling.
- Review transitions and `figure_type` derivation.
- B1 source/hash preservation and no-overwrite behavior.

### Integration tests

- A fake VLM client consumes recorded responses and proves one client is reused
  for a batch.
- The Q18 crop produces a parseable proposal and a human-reviewable B2 asset.
- A recorded invalid response produces `failed` without modifying B1 output.
- Existing Phase B1 tests remain green without GPU/model downloads.

### Acceptance criteria

1. Q18 B1 crop hash, bbox, provenance and parent linkage are byte-for-byte
   preserved in the B2 artifact.
2. The Qwen response is validated into the controlled taxonomy or is recorded
   as an explicit failure/unknown state.
3. Proposed and reviewed classifications are separate and auditable.
4. No B2 path invokes OCR rendering, answer reasoning, embeddings or Qdrant.
5. Focused B1 and B2 tests pass; no unrelated Track A output changes.

## 10. Follow-up boundary

After B2 is implemented and reviewed on a small sample, B3 may reuse the same
Qwen client for visible-label OCR with its existing OCR contract. B3 must remain
a separate stage and must not use B2's semantic proposal as OCR text.
