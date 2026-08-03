# Figure Phase B2 Qwen Semantic Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a local Qwen3-VL-8B-Instruct 4-bit semantic classifier for preserved Figure assets, with strict taxonomy validation, auditable proposal/review states, atomic B2 bundles and no changes to the B1 crop contract.

**Architecture:** Keep 2_生產線/src/figure_pipeline/ isolated from Track A OCR. Add strict B2 taxonomy models, a crop-only Qwen prompt/parser, an atomic runner that reuses one existing Qwen client per batch, and a separate review publisher. B1 bundles remain immutable; each B2 command writes a new bundle containing the unchanged crop files and a versioned figure_asset.json.

**Tech Stack:** Python 3.12, Pydantic v2, Pillow, existing local Transformers Qwen3-VL 4-bit client, pytest, Ruff, YAML configuration.

---

## Scope and file map

This is one coherent B2 subsystem: model contract, inference, review and CLI
share one artifact schema and are tested together. It does not include B3 OCR,
B4 structure extraction, embeddings or Qdrant.

Files to create:

- 2_生產線/src/figure_pipeline/classification_models.py 鈥?controlled taxonomy and B2 asset models.
- 2_生產線/src/figure_pipeline/classification_prompt.py 鈥?versioned crop-only Qwen prompt.
- 2_生產線/src/figure_pipeline/classification_parser.py 鈥?strict one-object JSON parser.
- 2_生產線/src/figure_pipeline/classification_runner.py 鈥?B1 validation, Qwen inference, atomic B2 publication and batch client reuse.
- 2_生產線/src/figure_pipeline/classification_review.py 鈥?reviewed/corrected/rejected B2 publication.
- 2_生產線/src/figure_pipeline/classification_cli.py 鈥?thin propose and review command implementation.
- 2_生產線/_script/phase_b2_figure_classify.py 鈥?executable wrapper for the B2 CLI.
- 2_生產線/tests/figure_pipeline/test_classification_models.py 鈥?taxonomy and B2 schema tests.
- 2_生產線/tests/figure_pipeline/test_classification_parser.py 鈥?parser and prompt-contract tests.
- 2_生產線/tests/figure_pipeline/test_classification_runner.py 鈥?fake-VLM and atomic bundle tests.
- 2_生產線/tests/figure_pipeline/test_classification_review.py 鈥?review transition tests.
- 2_生產線/tests/figure_pipeline/test_classification_cli.py 鈥?CLI argument and wiring tests.
- 2_生產線/tests/figure_pipeline/fixtures/qwen_geometry_response.txt 鈥?recorded valid Qwen response.
- 2_生產線/tests/figure_pipeline/fixtures/qwen_invalid_response.txt 鈥?recorded malformed response.

Files to modify:

- 2_生產線/src/ocr_pipeline/vlm_client.py 鈥?add an optional close() implementation for releasing Qwen resources after B2 runs; preserve the existing VlmClient.generate() contract.
- 2_生產線/config/ocr_pipeline.yaml 鈥?add B2 token/prompt settings without changing the OCR defaults.
- 3.分析結果/docs/figure_pipeline/progress.md 鈥?record B2 implementation and verification evidence.
- 3.分析結果/docs/FIGURE_PIPELINE_HANDOFF.md 鈥?append the B2 status and output contract while preserving its existing Track A/B1 sections.

## Task 1: Lock the taxonomy and B2 Pydantic models

Files:
- Create: 2_生產線/src/figure_pipeline/classification_models.py
- Create: 2_生產線/tests/figure_pipeline/test_classification_models.py

- [ ] Step 1: Write failing taxonomy tests

Create tests that require the approved family/subtype contract:

    from __future__ import annotations

    import pytest
    from pydantic import ValidationError

    from figure_pipeline.classification_models import (
        ClassifiedFigureAsset,
        ClassificationProposal,
        FigureClassification,
        ReviewedClassification,
    )
    from tests.figure_pipeline.helpers import valid_asset_dict


    def valid_proposal_dict() -> dict:
        return {
            "visual_family": "geometry",
            "subtype": "triangle",
            "secondary_tags": [],
            "confidence": 0.91,
            "evidence": ["Three visible straight edges form a triangle"],
            "needs_review": True,
            "model_id": "Qwen/Qwen3-VL-8B-Instruct",
            "quantization": "4-bit",
            "prompt_version": "figure-b2-v1",
        }


    def test_proposal_accepts_family_compatible_subtype() -> None:
        proposal = ClassificationProposal.model_validate(valid_proposal_dict())

        assert proposal.visual_family == "geometry"
        assert proposal.subtype == "triangle"


    def test_proposal_rejects_unknown_subtype() -> None:
        data = valid_proposal_dict()
        data["subtype"] = "hexagon_not_in_contract"

        with pytest.raises(ValidationError):
            ClassificationProposal.model_validate(data)


    def test_proposal_rejects_duplicate_or_unknown_secondary_tags() -> None:
        data = valid_proposal_dict()
        data["secondary_tags"] = ["statistical_chart", "statistical_chart"]

        with pytest.raises(ValidationError):
            ClassificationProposal.model_validate(data)

        data["secondary_tags"] = ["unknown"]
        with pytest.raises(ValidationError):
            ClassificationProposal.model_validate(data)


    def test_b2_asset_preserves_b1_source_and_has_pending_classification() -> None:
        b1 = valid_asset_dict()
        b2 = dict(b1)
        b2["schema_version"] = "1.1"
        b2["pipeline_version"] = "figure-b2-v1"
        b2["classification"] = {
            "proposed": valid_proposal_dict(),
            "reviewed": None,
            "status": "pending",
        }

        asset = ClassifiedFigureAsset.model_validate(b2)

        assert asset.source.bbox == (700, 350, 1280, 760)
        assert asset.figure_type == "unknown"
        assert asset.classification.status == "pending"


    def test_reviewed_classification_requires_unknown_for_rejection() -> None:
        data = {
            "visual_family": "geometry",
            "subtype": "triangle",
            "secondary_tags": [],
            "status": "rejected",
            "reviewer": "human-1",
            "source_proposal_id": "asset:figure-b2-v1",
        }

        with pytest.raises(ValidationError):
            ReviewedClassification.model_validate(data)


    def test_classification_status_matches_review_record() -> None:
        proposal = ClassificationProposal.model_validate(valid_proposal_dict())
        data = {
            "proposed": proposal.model_dump(mode="json"),
            "reviewed": None,
            "status": "approved",
        }

        with pytest.raises(ValidationError):
            FigureClassification.model_validate(data)

- [ ] Step 2: Run the model tests and verify the initial failure

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline/test_classification_models.py -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-models-red; exit $LASTEXITCODE

Expected: collection fails with ModuleNotFoundError for
figure_pipeline.classification_models.

- [ ] Step 3: Implement the strict taxonomy models

Create 2_生產線/src/figure_pipeline/classification_models.py with these exact
invariants. Keep FigureAsset in models.py unchanged so all B1 validation tests
continue to exercise the original schema_version 1.0 model.

    from __future__ import annotations

    from typing import Literal

    from pydantic import Field, model_validator

    from .models import FigureAsset, StrictModel

    VisualFamily = Literal[
        "geometry",
        "coordinate_graph",
        "function_graph",
        "statistical_chart",
        "table",
        "physical_diagram",
        "illustration",
        "unknown",
    ]

    SUBTYPE_BY_FAMILY: dict[str, frozenset[str]] = {
        "geometry": frozenset(
            {
                "triangle",
                "quadrilateral",
                "circle",
                "polygon",
                "solid",
                "angle",
                "transformation",
                "other",
            }
        ),
        "coordinate_graph": frozenset(
            {"point_plot", "line_segment", "locus", "vector", "other"}
        ),
        "function_graph": frozenset(
            {
                "linear",
                "quadratic",
                "polynomial",
                "piecewise",
                "trigonometric",
                "exponential",
                "other",
            }
        ),
        "statistical_chart": frozenset(
            {"bar", "line", "pie", "scatter", "box", "histogram", "other"}
        ),
        "table": frozenset(
            {"data_table", "frequency_table", "value_table", "other"}
        ),
        "physical_diagram": frozenset(
            {"flowchart", "circuit", "mechanical", "engineering", "chemistry", "other"}
        ),
        "illustration": frozenset({"map", "photo", "decorative", "other"}),
        "unknown": frozenset({"unclassified"}),
    }


    class ClassificationProposal(StrictModel):
        visual_family: VisualFamily
        subtype: str = Field(min_length=1)
        secondary_tags: list[VisualFamily] = Field(default_factory=list, max_length=3)
        confidence: float = Field(ge=0.0, le=1.0)
        evidence: list[str] = Field(min_length=1, max_length=3)
        needs_review: bool = True
        model_id: str = Field(min_length=1)
        quantization: Literal["4-bit"] = "4-bit"
        prompt_version: Literal["figure-b2-v1"] = "figure-b2-v1"

        @model_validator(mode="after")
        def validate_taxonomy(self) -> ClassificationProposal:
            allowed_subtypes = SUBTYPE_BY_FAMILY[self.visual_family]
            if self.subtype not in allowed_subtypes:
                raise ValueError(
                    f"subtype {self.subtype!r} is not valid for {self.visual_family!r}"
                )
            if len(set(self.secondary_tags)) != len(self.secondary_tags):
                raise ValueError("secondary_tags must be unique")
            if "unknown" in self.secondary_tags:
                raise ValueError("unknown cannot be a secondary tag")
            if self.visual_family in self.secondary_tags:
                raise ValueError("primary visual_family cannot repeat in secondary_tags")
            return self


    class ReviewedClassification(StrictModel):
        visual_family: VisualFamily
        subtype: str = Field(min_length=1)
        secondary_tags: list[VisualFamily] = Field(default_factory=list, max_length=3)
        status: Literal["approved", "corrected", "rejected"]
        reviewer: str = Field(min_length=1)
        source_proposal_id: str = Field(min_length=1)

        @model_validator(mode="after")
        def validate_review(self) -> ReviewedClassification:
            allowed_subtypes = SUBTYPE_BY_FAMILY[self.visual_family]
            if self.subtype not in allowed_subtypes:
                raise ValueError("review subtype is incompatible with visual_family")
            if len(set(self.secondary_tags)) != len(self.secondary_tags):
                raise ValueError("secondary_tags must be unique")
            if "unknown" in self.secondary_tags or self.visual_family in self.secondary_tags:
                raise ValueError("review secondary_tags contains an invalid family")
            if self.status == "rejected" and self.visual_family != "unknown":
                raise ValueError("rejected reviews must use visual_family=unknown")
            if self.status != "rejected" and self.visual_family == "unknown":
                raise ValueError("approved/corrected reviews cannot use unknown")
            return self


    class FigureClassification(StrictModel):
        proposed: ClassificationProposal | None = None
        reviewed: ReviewedClassification | None = None
        status: Literal[
            "pending", "approved", "corrected", "rejected", "failed"
        ] = "pending"
        response_path: str | None = None
        response_sha256: str | None = None
        error: str | None = None

        @model_validator(mode="after")
        def validate_state(self) -> FigureClassification:
            if self.status == "pending" and self.reviewed is not None:
                raise ValueError("pending classification cannot have reviewed data")
            if self.status in {"approved", "corrected", "rejected"}:
                if self.reviewed is None or self.reviewed.status != self.status:
                    raise ValueError("reviewed status must match classification status")
            if self.status == "failed" and self.proposed is not None:
                raise ValueError("failed classification cannot contain a proposal")
            if self.status != "failed" and self.error is not None:
                raise ValueError("error is only valid for failed classification")
            return self


    class ClassifiedFigureAsset(FigureAsset):
        schema_version: Literal["1.1"] = "1.1"
        pipeline_version: Literal["figure-b2-v1"] = "figure-b2-v1"
        figure_type: str = "unknown"
        classification: FigureClassification

        @classmethod
        def from_b1(
            cls,
            asset: FigureAsset,
            classification: FigureClassification,
            *,
            figure_type: str = "unknown",
        ) -> ClassifiedFigureAsset:
            payload = asset.model_dump(mode="json")
            payload.update(
                {
                    "schema_version": "1.1",
                    "pipeline_version": "figure-b2-v1",
                    "figure_type": figure_type,
                    "classification": classification.model_dump(mode="json"),
                }
            )
            return cls.model_validate(payload)

- [ ] Step 4: Run the model tests and the unchanged B1 model tests

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline/test_classification_models.py 2_生產線/tests/figure_pipeline/test_models.py -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-models-green; exit $LASTEXITCODE

Expected: all new model tests and the existing B1 model tests pass.

- [ ] Step 5: Commit the isolated model contract

Run:

    git add figure/2_生產線/src/figure_pipeline/classification_models.py figure/2_生產線/tests/figure_pipeline/test_classification_models.py
    git commit -m "feat: add figure classification models"

## Task 2: Add the versioned prompt and strict response parser

Files:
- Create: 2_生產線/src/figure_pipeline/classification_prompt.py
- Create: 2_生產線/src/figure_pipeline/classification_parser.py
- Create: 2_生產線/tests/figure_pipeline/test_classification_parser.py
- Create: 2_生產線/tests/figure_pipeline/fixtures/qwen_geometry_response.txt
- Create: 2_生產線/tests/figure_pipeline/fixtures/qwen_invalid_response.txt

- [ ] Step 1: Add parser tests before implementation

Create qwen_geometry_response.txt with this exact JSON:

    {
      "visual_family": "geometry",
      "subtype": "triangle",
      "secondary_tags": [],
      "confidence": 0.91,
      "evidence": [
        "Three visible straight edges form a triangle",
        "Angle markers are present"
      ],
      "needs_review": true
    }

Create qwen_invalid_response.txt with a JSON object wrapped in a Markdown
JSON code fence. The file must begin with three backtick characters followed by
json, contain {"visual_family": "geometry", "subtype": "not-a-real-subtype"},
and end with three backtick characters.

Add tests:

    from pathlib import Path

    import pytest

    from figure_pipeline.classification_parser import (
        ClassificationParseError,
        parse_classification_response,
    )


    FIXTURES = Path(__file__).parent / "fixtures"


    def test_parser_adds_runtime_metadata_to_valid_response() -> None:
        raw = (FIXTURES / "qwen_geometry_response.txt").read_text(encoding="utf-8")

        result = parse_classification_response(
            raw,
            model_id="Qwen/Qwen3-VL-8B-Instruct",
            quantization="4-bit",
            prompt_version="figure-b2-v1",
        )

        assert result.visual_family == "geometry"
        assert result.model_id == "Qwen/Qwen3-VL-8B-Instruct"
        assert result.prompt_version == "figure-b2-v1"


    @pytest.mark.parametrize(
        "raw",
        [
            (FIXTURES / "qwen_invalid_response.txt").read_text(encoding="utf-8"),
            "classification: geometry",
            '{"visual_family": "geometry", "subtype": "triangle", "extra": 1}',
            "[]",
        ],
    )
    def test_parser_rejects_non_contract_responses(raw: str) -> None:
        with pytest.raises(ClassificationParseError):
            parse_classification_response(
                raw,
                model_id="Qwen/Qwen3-VL-8B-Instruct",
                quantization="4-bit",
                prompt_version="figure-b2-v1",
            )

- [ ] Step 2: Run parser tests to verify the initial failure

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline/test_classification_parser.py -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-parser-red; exit $LASTEXITCODE

Expected: collection fails because the prompt/parser modules do not exist.

- [ ] Step 3: Implement the crop-only prompt

Create classification_prompt.py. The prompt must list the exact allowed labels
and must forbid solving the question, returning OCR text, prose, Markdown
fences or invented subtypes.

    from .classification_models import SUBTYPE_BY_FAMILY

    FIGURE_CLASSIFICATION_PROMPT_VERSION = "figure-b2-v1"

    _FAMILIES = (
        "geometry, coordinate_graph, function_graph, statistical_chart, "
        "table, physical_diagram, illustration, unknown"
    )
    _SUBTYPES = "; ".join(
        f"{family}: {', '.join(sorted(values))}"
        for family, values in SUBTYPE_BY_FAMILY.items()
    )

    FIGURE_CLASSIFICATION_PROMPT = f"""Inspect only the supplied figure crop.
Choose exactly one visual_family from: {_FAMILIES}.
Choose one compatible subtype from this list: {_SUBTYPES}.
Use secondary_tags only for additional visibly present families; use at most three.
If the crop is ambiguous, incomplete, or not a supported figure, use
visual_family="unknown" and subtype="unclassified".
Do not solve the math problem. Do not transcribe OCR. Do not return Markdown,
code fences, commentary, or keys outside the required JSON object.
Return exactly this JSON shape:
{{"visual_family":"unknown", "subtype":"unclassified", "secondary_tags":[],
  "confidence":0.0, "evidence":["short observable cue"], "needs_review":true}}
The confidence is a number from 0 to 1. Evidence must contain one to three
short observable cues. needs_review must be true."""

- [ ] Step 4: Implement the strict parser without using strip_fences

Create classification_parser.py. Reject fenced output before json.loads so a
model that ignored the prompt is recorded as a failure instead of silently
normalized.

    from __future__ import annotations

    import json
    from typing import Any

    from pydantic import ValidationError

    from .classification_models import ClassificationProposal


    class ClassificationParseError(ValueError):
        pass


    def parse_classification_response(
        raw: str,
        *,
        model_id: str,
        quantization: str,
        prompt_version: str,
    ) -> ClassificationProposal:
        text = (raw or "").strip()
        fence = chr(96) * 3
        if not text or text.startswith(fence) or text.endswith(fence):
            raise ClassificationParseError("response must be one unfenced JSON object")
        try:
            payload: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ClassificationParseError("response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ClassificationParseError("response root must be a JSON object")
        payload = dict(payload)
        payload.update(
            {
                "model_id": model_id,
                "quantization": quantization,
                "prompt_version": prompt_version,
            }
        )
        try:
            return ClassificationProposal.model_validate(payload)
        except ValidationError as exc:
            raise ClassificationParseError("response violates B2 taxonomy") from exc

- [ ] Step 5: Run parser tests and prompt lint checks

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline/test_classification_parser.py -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-parser-green; exit $LASTEXITCODE
    uv run ruff check 2_生產線/src/figure_pipeline/classification_prompt.py 2_生產線/src/figure_pipeline/classification_parser.py 2_生產線/tests/figure_pipeline/test_classification_parser.py

Expected: parser tests pass and Ruff reports no errors.

- [ ] Step 6: Commit the prompt/parser contract

Run:

    git add figure/2_生產線/src/figure_pipeline/classification_prompt.py figure/2_生產線/src/figure_pipeline/classification_parser.py figure/2_生產線/tests/figure_pipeline/test_classification_parser.py figure/2_生產線/tests/figure_pipeline/fixtures/qwen_geometry_response.txt figure/2_生產線/tests/figure_pipeline/fixtures/qwen_invalid_response.txt
    git commit -m "feat: add strict figure classification prompt parser"

## Task 3: Implement inference, B1 verification and atomic B2 publication

Files:
- Create: 2_生產線/src/figure_pipeline/classification_runner.py
- Create: 2_生產線/tests/figure_pipeline/test_classification_runner.py
- Modify: 2_生產線/src/ocr_pipeline/vlm_client.py

- [ ] Step 1: Write fake-client tests for one-shot and batch behavior

The fake client must expose model_name and load_in_4bit metadata, record calls,
and return the valid fixture response. Define make_b1_bundle(tmp_path) with the existing B1 helper pattern, valid_response() by reading qwen_geometry_response.txt, and invalid_response() by reading qwen_invalid_response.txt. Test that the runner reads the B1 crop,
passes only the crop path to generate, writes the B2 asset, copies the source
crop, and reuses one client for two sequential assets.

    class FakeVlmClient:
        model_name = "Qwen/Qwen3-VL-8B-Instruct"
        load_in_4bit = True

        def __init__(self, response: str) -> None:
            self.response = response
            self.calls: list[tuple[str, Path, int]] = []

        def generate(
            self,
            prompt: str,
            image_path: Path | None = None,
            *,
            max_new_tokens: int | None = None,
        ) -> str:
            assert image_path is not None
            self.calls.append((prompt, image_path, int(max_new_tokens or 0)))
            return self.response


    def test_classify_bundle_preserves_crop_and_publishes_b2_asset(tmp_path: Path) -> None:
        source_dir = make_b1_bundle(tmp_path)
        destination = tmp_path / "q018-b2"
        client = FakeVlmClient(valid_response())

        asset = classify_bundle(
            source_dir,
            destination,
            client=client,
            max_new_tokens=256,
        )

        assert asset.schema_version == "1.1"
        assert asset.pipeline_version == "figure-b2-v1"
        assert asset.classification.status == "pending"
        assert asset.figure_type == "unknown"
        assert (destination / "assets/q018_fig01.png").read_bytes() == (
            source_dir / "assets/q018_fig01.png"
        ).read_bytes()
        assert len(client.calls) == 1


    def test_classify_many_reuses_the_same_client(tmp_path: Path) -> None:
        first = make_b1_bundle(tmp_path / "first")
        second = make_b1_bundle(tmp_path / "second")
        client = FakeVlmClient(valid_response())

        assets = classify_many(
            [(first, tmp_path / "first-b2"), (second, tmp_path / "second-b2")],
            client=client,
            max_new_tokens=256,
        )

        assert len(assets) == 2
        assert len(client.calls) == 2
        assert all(call[2] == 256 for call in client.calls)


    def test_invalid_response_publishes_failed_classification_and_raw_response(
        tmp_path: Path,
    ) -> None:
        source_dir = make_b1_bundle(tmp_path)
        destination = tmp_path / "q018-b2-failed"
        client = FakeVlmClient(invalid_response())

        asset = classify_bundle(
            source_dir,
            destination,
            client=client,
            max_new_tokens=256,
        )

        assert asset.classification.status == "failed"
        assert asset.classification.proposed is None
        assert asset.figure_type == "unknown"
        assert (destination / "classification_response.txt").read_text(
            encoding="utf-8"
        ) == invalid_response()


    def test_hash_mismatch_fails_without_destination(tmp_path: Path) -> None:
        source_dir = make_b1_bundle(tmp_path)
        asset_path = source_dir / "figure_asset.json"
        data = json.loads(asset_path.read_text(encoding="utf-8"))
        data["source"]["sha256"] = "c" * 64
        asset_path.write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(ValueError, match="hash"):
            classify_bundle(
                source_dir,
                tmp_path / "q018-b2",
                client=FakeVlmClient(valid_response()),
                max_new_tokens=256,
            )

        assert not (tmp_path / "q018-b2").exists()

- [ ] Step 2: Run runner tests to verify the initial failure

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline/test_classification_runner.py -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-runner-red; exit $LASTEXITCODE

Expected: collection fails because classification_runner.py does not exist.

- [ ] Step 3: Add an explicit Qwen close method without changing generate()

In 2_生產線/src/ocr_pipeline/vlm_client.py, add this method to QwenVlClient after
generate(). Do not add close() to the VlmClient Protocol, because existing fake
OCR clients only implement generate().

    def close(self) -> None:
        self.model = None
        self.processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

- [ ] Step 4: Implement the atomic runner

Create classification_runner.py with these public functions:

    def classify_bundle(
        source_dir: Path,
        destination: Path,
        *,
        client: VlmClient,
        max_new_tokens: int = 256,
        prompt_version: str = "figure-b2-v1",
    ) -> ClassifiedFigureAsset:

    def classify_many(
        jobs: Sequence[tuple[Path, Path]],
        *,
        client: VlmClient,
        max_new_tokens: int = 256,
        prompt_version: str = "figure-b2-v1",
    ) -> list[ClassifiedFigureAsset]:

Implementation rules:

1. Refuse an existing destination before opening the model.
2. Validate source_dir/figure_asset.json using FigureAsset.model_validate_json.
3. Resolve asset.source.crop_path under source_dir and verify its SHA-256 with
   the existing figure_pipeline.proposal.sha256_file helper.
4. Call client.generate(FIGURE_CLASSIFICATION_PROMPT, image_path=crop_path,
   max_new_tokens=max_new_tokens). Do not pass question text or answer choices.
5. Add model metadata from client.model_name and client.load_in_4bit, then call
   parse_classification_response.
6. For a valid response, create FigureClassification(status="pending",
   proposed=proposal).
7. For ClassificationParseError, save the exact raw text as
   classification_response.txt in the staging directory, hash it, and create
   FigureClassification(status="failed", error=str(exc), response_path="classification_response.txt").
8. For model-loading or generate exceptions, remove the staging directory and
   re-raise without publishing a B2 bundle.
9. Copy the complete B1 bundle into a sibling staging directory, replace only
   figure_asset.json with ClassifiedFigureAsset.from_b1(asset, classification), and verify the
   copied crop SHA-256 before directory rename.
10. classify_many must iterate in input order and use the same client object for
    every job.

The staging name must be
destination.parent / (f".{destination.name}.staging-{uuid.uuid4().hex}").
Use shutil.copytree(source_dir, stage, dirs_exist_ok=True), write UTF-8 JSON
with ensure_ascii=False and sort_keys=True, then rename stage to destination.

- [ ] Step 5: Run runner tests, B1 tests and Ruff

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline/test_classification_runner.py 2_生產線/tests/figure_pipeline/test_preserve.py 2_生產線/tests/figure_pipeline/test_models.py -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-runner-green; exit $LASTEXITCODE
    uv run ruff check 2_生產線/src/figure_pipeline/classification_runner.py 2_生產線/src/ocr_pipeline/vlm_client.py 2_生產線/tests/figure_pipeline/test_classification_runner.py

Expected: new runner tests and existing B1 tests pass; Ruff reports no errors.

- [ ] Step 6: Commit inference and atomic publication

Run:

    git add figure/2_生產線/src/figure_pipeline/classification_runner.py figure/2_生產線/src/ocr_pipeline/vlm_client.py figure/2_生產線/tests/figure_pipeline/test_classification_runner.py
    git commit -m "feat: add qwen figure classification runner"

## Task 4: Implement reviewed, corrected and rejected publication

Files:
- Create: 2_生產線/src/figure_pipeline/classification_review.py
- Create: 2_生產線/tests/figure_pipeline/test_classification_review.py

- [ ] Step 1: Write review transition tests

Define make_pending_b2_bundle(tmp_path), make_approved_b2_bundle(tmp_path), proposal_id(source_dir), and approved_decision(source_dir) in this test module; each helper creates or reads the exact B2 JSON described in Task 3 and returns a Path or ReviewedClassification. Test all three allowed decisions against a pending B2 bundle:

    def test_approve_derives_figure_type_and_preserves_source(tmp_path: Path) -> None:
        source_dir = make_pending_b2_bundle(tmp_path)
        destination = tmp_path / "approved"

        asset = review_bundle(
            source_dir,
            destination,
            ReviewedClassification(
                visual_family="geometry",
                subtype="triangle",
                secondary_tags=[],
                status="approved",
                reviewer="human-1",
                source_proposal_id=proposal_id(source_dir),
            ),
        )

        assert asset.figure_type == "geometry"
        assert asset.classification.status == "approved"
        assert asset.classification.reviewed is not None
        assert (destination / "assets/q018_fig01.png").is_file()


    def test_corrected_review_replaces_proposal_without_mutating_source(
        tmp_path: Path,
    ) -> None:
        source_dir = make_pending_b2_bundle(tmp_path)
        destination = tmp_path / "corrected"

        asset = review_bundle(
            source_dir,
            destination,
            ReviewedClassification(
                visual_family="coordinate_graph",
                subtype="point_plot",
                secondary_tags=["geometry"],
                status="corrected",
                reviewer="human-2",
                source_proposal_id=proposal_id(source_dir),
            ),
        )

        assert asset.figure_type == "coordinate_graph"
        original = json.loads(
            (source_dir / "figure_asset.json").read_text(encoding="utf-8")
        )
        assert original["classification"]["reviewed"] is None


    def test_rejected_review_uses_unknown_and_stays_unresolved(tmp_path: Path) -> None:
        source_dir = make_pending_b2_bundle(tmp_path)
        destination = tmp_path / "rejected"

        asset = review_bundle(
            source_dir,
            destination,
            ReviewedClassification(
                visual_family="unknown",
                subtype="unclassified",
                secondary_tags=[],
                status="rejected",
                reviewer="human-3",
                source_proposal_id=proposal_id(source_dir),
            ),
        )

        assert asset.figure_type == "unknown"
        assert asset.classification.status == "rejected"


    def test_review_requires_pending_proposal_and_new_destination(tmp_path: Path) -> None:
        source_dir = make_approved_b2_bundle(tmp_path)

        with pytest.raises(ValueError, match="pending"):
            review_bundle(
                source_dir,
                tmp_path / "invalid-review",
                approved_decision(source_dir),
            )

        destination = tmp_path / "existing"
        destination.mkdir()
        with pytest.raises(FileExistsError):
            review_bundle(source_dir, destination, approved_decision(source_dir))

- [ ] Step 2: Run review tests to verify the initial failure

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline/test_classification_review.py -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-review-red; exit $LASTEXITCODE

Expected: collection fails because classification_review.py does not exist.

- [ ] Step 3: Implement review_bundle with source proposal binding

Create classification_review.py with:

    def review_bundle(
        source_dir: Path,
        destination: Path,
        decision: ReviewedClassification,
    ) -> ClassifiedFigureAsset:

The function must:

1. Refuse an existing destination.
2. Load ClassifiedFigureAsset from source_dir/figure_asset.json.
3. Require classification.status == "pending" and a non-null proposed object.
4. Require decision.source_proposal_id to equal
   f"{asset.asset_id}:{asset.classification.proposed.prompt_version}".
5. Copy the complete source bundle to a UUID staging directory.
6. Set classification.reviewed to decision and status to decision.status.
7. Set figure_type to decision.visual_family for approved/corrected, otherwise
   unknown for rejected.
8. Validate the copied crop hash and publish by directory rename.

Do not mutate source_dir and do not alter the existing validation.reviewed flag;
semantic review status lives in classification.status.

- [ ] Step 4: Run review tests and commit

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline/test_classification_review.py -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-review-green; exit $LASTEXITCODE
    uv run ruff check 2_生產線/src/figure_pipeline/classification_review.py 2_生產線/tests/figure_pipeline/test_classification_review.py

Expected: all review transition tests pass and Ruff reports no errors.

Commit:

    git add figure/2_生產線/src/figure_pipeline/classification_review.py figure/2_生產線/tests/figure_pipeline/test_classification_review.py
    git commit -m "feat: add auditable figure classification review"

## Task 5: Add the standalone B2 CLI and configuration

Files:
- Create: 2_生產線/src/figure_pipeline/classification_cli.py
- Create: 2_生產線/_script/phase_b2_figure_classify.py
- Create: 2_生產線/tests/figure_pipeline/test_classification_cli.py
- Modify: 2_生產線/config/ocr_pipeline.yaml

- [ ] Step 1: Write CLI tests with a monkeypatched local client

Test that propose builds one client, passes the configured 256-token budget and publishes a B2 output; define a local FakeVlmClient with the Task 3 generate signature. Test that review does not load a model and rejects invalid combinations.

    def test_cli_propose_uses_configured_client_once(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_dir = make_b1_bundle(tmp_path)
        destination = tmp_path / "cli-b2"
        fake = FakeVlmClient(valid_response())
        monkeypatch.setattr(
            "figure_pipeline.classification_cli.build_vlm_client",
            lambda cfg: fake,
        )
        monkeypatch.setattr(
            "figure_pipeline.classification_cli.load_ocr_config",
            lambda path=None: {
                "figure_classification": {
                    "max_new_tokens": 256,
                    "prompt_version": "figure-b2-v1",
                }
            },
        )

        exit_code = main(
            [
                "propose",
                "--asset",
                str(source_dir),
                "--out",
                str(destination),
            ]
        )

        assert exit_code == 0
        assert (destination / "figure_asset.json").is_file()
        assert fake.calls[0][2] == 256


    def test_cli_review_requires_labels_for_approval(tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="visual-family"):
            main(
                [
                    "review",
                    "--asset",
                    str(tmp_path / "pending"),
                    "--out",
                    str(tmp_path / "reviewed"),
                    "--reviewer",
                    "human-1",
                    "--status",
                    "approved",
                ]
            )

- [ ] Step 2: Update configuration with a B2-only block

Append this block to 2_生產線/config/ocr_pipeline.yaml without changing layout,
engines, vlm or Track A settings:

    figure_classification:
      enabled: true
      max_new_tokens: 256
      prompt_version: "figure-b2-v1"

- [ ] Step 3: Implement the thin CLI and wrapper

classification_cli.py must expose build_parser() and main(argv=None). The
subcommands and required arguments are:

    propose --asset PATH --out PATH [--config PATH]
    review --asset PATH --out PATH --reviewer TEXT --status approved|corrected|rejected
           [--visual-family FAMILY] [--subtype SUBTYPE] [--secondary-tag FAMILY]

For propose, load config with load_ocr_config, build one client with
build_vlm_client, read figure_classification.max_new_tokens and
figure_classification.prompt_version, call classify_bundle, and call
getattr(client, "close", None) in a finally block.

For review, require visual-family and subtype for approved/corrected; reject
those flags for rejected and construct unknown/unclassified automatically.
Allow repeated --secondary-tag and pass the resulting list to
ReviewedClassification. Do not load Qwen for review.

The script wrapper is exactly:

    from figure_pipeline.classification_cli import main

    if __name__ == "__main__":
        raise SystemExit(main())

- [ ] Step 4: Run CLI tests, existing B1 CLI tests and Ruff

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline/test_classification_cli.py 2_生產線/tests/figure_pipeline/test_cli.py -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-cli-green; exit $LASTEXITCODE
    uv run ruff check 2_生產線/src/figure_pipeline/classification_cli.py 2_生產線/_script/phase_b2_figure_classify.py 2_生產線/tests/figure_pipeline/test_classification_cli.py

Expected: new and existing CLI tests pass and Ruff reports no errors.

- [ ] Step 5: Commit the CLI and configuration

Run:

    git add figure/2_生產線/src/figure_pipeline/classification_cli.py figure/2_生產線/_script/phase_b2_figure_classify.py figure/2_生產線/config/ocr_pipeline.yaml figure/2_生產線/tests/figure_pipeline/test_classification_cli.py
    git commit -m "feat: add figure classification cli"

## Task 6: Add the real-sample acceptance path and documentation

Files:
- Create: 2_生產線/tests/figure_pipeline/test_b2_acceptance.py
- Modify: 3.分析結果/docs/figure_pipeline/progress.md
- Modify: 3.分析結果/docs/FIGURE_PIPELINE_HANDOFF.md

- [ ] Step 1: Add a recorded-response acceptance test

Use the existing published sample`n3.分析結果/output/figure_pipeline/2015p2/q018/figure_asset.json as the B1 input. Define the same local FakeVlmClient and valid_response helper used in Task 3, return qwen_geometry_response.txt, and assert:

    def test_q18_b2_acceptance_keeps_identity_and_hashes(tmp_path: Path) -> None:
        source = Path("3.分析結果/output/figure_pipeline/2015p2/q018")
        destination = tmp_path / "q018-b2"
        asset = classify_bundle(
            source,
            destination,
            client=FakeVlmClient(valid_response()),
            max_new_tokens=256,
        )

        original = FigureAsset.model_validate_json(
            (source / "figure_asset.json").read_text(encoding="utf-8")
        )
        assert asset.asset_id == original.asset_id
        assert asset.parent_question_id == original.parent_question_id
        assert asset.source.bbox == original.source.bbox
        assert asset.source.sha256 == original.source.sha256
        assert sha256_file(destination / asset.source.crop_path) == asset.source.sha256
        assert asset.classification.proposed is not None
        assert asset.classification.proposed.visual_family == "geometry"

- [ ] Step 2: Run focused and full Figure verification

Run the focused suite:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-all; exit $LASTEXITCODE

Expected: all B1 and B2 Figure tests pass.

Run lint and compile checks:

    uv run ruff check 2_生產線/src/figure_pipeline 2_生產線/tests/figure_pipeline 2_生產線/_script/phase_b2_figure_classify.py
    uv run python -m compileall -q 2_生產線/src/figure_pipeline 2_生產線/_script/phase_b2_figure_classify.py

Expected: Ruff exits 0 and compileall emits no errors.

- [ ] Step 3: Run the real local Qwen proposal on the accepted sample

Only after the focused tests pass, run this GPU command once:

    uv run python 2_生產線/_script/phase_b2_figure_classify.py propose --asset 3.分析結果/output/figure_pipeline/2015p2/q018 --out 3.分析結果/output/figure_pipeline/2015p2/q018-b2

Expected: one new output directory is published, the source B1 directory is
unchanged, and 3.分析結果/output/figure_pipeline/2015p2/q018-b2/figure_asset.json contains
schema_version 1.1, pipeline_version figure-b2-v1, a pending proposed
classification and the original crop hash.

- [ ] Step 4: Record verification evidence in project docs

Append to 3.分析結果/docs/figure_pipeline/progress.md:

    ## 2026-08-02 鈥?Phase B2 Qwen semantic classification

    Status: implemented on the recorded-response fixture and Q18 acceptance sample.
    Runtime: local Qwen/Qwen3-VL-8B-Instruct, 4-bit, sequential client reuse.
    Contract: schema_version 1.1, pipeline_version figure-b2-v1,
    classification.proposed/reviewed, human review required.
    Verification: focused Figure tests, Ruff, compileall and Q18 source/hash checks.

Append the matching B2 status, CLI commands and out-of-scope B3/B4 boundary to
3.分析結果/docs/FIGURE_PIPELINE_HANDOFF.md. Keep the handoff's existing statement that
MinerU owns layout/bbox and Qwen is already used locally for OCR.

- [ ] Step 5: Commit acceptance and documentation

Run:

    git add figure/2_生產線/tests/figure_pipeline/test_b2_acceptance.py figure/3.分析結果/docs/figure_pipeline/progress.md figure/3.分析結果/docs/FIGURE_PIPELINE_HANDOFF.md
    git commit -m "docs: record figure b2 qwen classification"

## Task 7: Final regression and handoff

Files:
- No new source files; verify all B2 and existing Track A boundaries.

- [ ] Step 1: Run the complete Figure suite again from a clean output target

Run:

    $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -m pytest 2_生產線/tests/figure_pipeline -q -p no:cacheprovider --basetemp .pytest-tmp-local/figure-b2-final; exit $LASTEXITCODE

Expected: every Figure test passes, including all existing B1 tests.

- [ ] Step 2: Confirm Track A regression boundary

Run the repository's existing Track A smoke command:

    $env:UV_CACHE_DIR=(Join-Path (Get-Location) '.uv-cache'); uv run python -m pytest 2_生產線/tests/test_check_compile_cli.py 2_生產線/tests/test_engines_pipeline_smoke.py -q -p no:cacheprovider; exit $LASTEXITCODE

Expected: no Track A test imports the B2 classifier and no Track A artifact
schema or renderer output changes.

- [ ] Step 3: Inspect the final change set

Run:

    git diff --check
    git status --short -- figure/2_生產線/src/figure_pipeline figure/2_生產線/src/ocr_pipeline/vlm_client.py figure/2_生產線/config/ocr_pipeline.yaml figure/2_生產線/_script/phase_b2_figure_classify.py figure/2_生產線/tests/figure_pipeline figure/3.分析結果/docs/figure_pipeline figure/3.分析結果/docs/FIGURE_PIPELINE_HANDOFF.md

Expected: diff --check is clean; only the planned B2 files are changed in the
Figure scope. Do not stage or revert unrelated existing worktree changes.

- [ ] Step 4: Hand off the implementation result

Report the B2 output directory, model ID/quantization, test commands and the
fact that classification.reviewed remains null until an explicit human
review command is run. The next available phase is B3 visible-label OCR; do
not start B3 in this plan.




