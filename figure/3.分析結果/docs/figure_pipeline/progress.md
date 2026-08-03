# Figure / Table Track B Progress

## 2026-07-31 — Phase B1 Asset Preservation

Status: implementation and one human-confirmed sample are complete.

### Scope delivered

- Added an isolated `2_生產線/src/figure_pipeline/` package; Track A OCR behavior remains
  unchanged.
- Added strict Phase B1 `FigureAsset`, source, provenance and proposal schemas.
- Added a read-only MinerU `PP-DocLayoutV2` figure proposal adapter.
- Added atomic proposal and final asset publication with no-overwrite behavior.
- Added manual bbox fallback using the same `FigureAsset` schema.
- Added a CLI at `2_生產線/_script/phase_b1_figure_asset.py`.

Phase B1 does not perform captions, classification, visible-label OCR, structured
geometry analysis, embeddings, Qdrant mutation or answer reasoning.

### Accepted sample

- Source document: `1_收集資料/data/sources/2015p2.pdf`
- Question: `hk-dse-2015-math-p2-q018`
- Page: `6`
- Upstream question crop:
  `1_收集資料/data/pdf_pages/2015p2/crops/p006_q018.png`
- MinerU detector: `mineru_pp_doclayout_v2`
- Human-confirmed candidate: `0`
- Figure bbox: `[678, 382, 1278, 735]`
- Bbox coordinate space: `question_crop_pixels`
- Asset ID: `hk-dse-2015-math-p2-q018-fig01`
- Proposal:
  `3.分析結果/output/figure_pipeline/2015p2/q018-proposal/proposal.json`
- Final asset JSON:
  `3.分析結果/output/figure_pipeline/2015p2/q018/figure_asset.json`
- Preserved question crop:
  `3.分析結果/output/figure_pipeline/2015p2/q018/question.png`
- Figure crop:
  `3.分析結果/output/figure_pipeline/2015p2/q018/assets/q018_fig01.png`

### Verification evidence

- Question crop SHA-256:
  `4f69cfa63828e86331545c9c912d1335bf884d63120d20c8bdf1fd4b0315341a`
- Figure crop SHA-256:
  `c7e9843ee365b7413cd6f2866dabc11688bd52b6f2bb8dba73eb3e264de84342`
- Both hashes were recomputed from the published files and matched
  `figure_asset.json`.
- `text_result.question_id == figure_result.parent_question_id` linkage is
  represented by the preserved parent ID
  `hk-dse-2015-math-p2-q018`.
- Figure unit suite: `19 passed`.
- Ruff: all checks passed.
- `py_compile`: exit code `0`.
- Track A aggregate SHA-256 before and after implementation:
  `4223E52BFFD7BD1A8F97C6A85F5EAC1AB6B48CCEF3D00F560853D86DB3F908E2`.

### Next phase

Phase B2 is asset classification. It must begin only after a separate scope and
acceptance design is approved.

## 2026-08-02 ? Phase B2 Qwen semantic classification

Status: implemented and verified on the recorded-response fixture and the Q18
acceptance sample.

Runtime contract: local Qwen/Qwen3-VL-8B-Instruct, 4-bit, sequential client
reuse; B2 assets use schema_version=1.1 and pipeline_version=figure-b2-v1.
classification.proposed remains pending until an explicit human review command
publishes classification.reviewed; B1 bundles remain immutable.

CLI:

- uv run python 2_生產線/_script/phase_b2_figure_classify.py propose --asset <b1-bundle> --out <b2-bundle>
- uv run python 2_生產線/_script/phase_b2_figure_classify.py review --asset <pending-b2> --out <reviewed-b2> --reviewer <name> --status approved|corrected|rejected

Verification: complete Figure focused suite 99 passed, CLI/B1 CLI suite
12 passed, recorded-response Q18 acceptance 1 passed, Ruff and compileall
clean. The recorded Q18 proposal preserves the original asset identity,
bbox and crop SHA-256.

Real local Qwen smoke: 3.分析結果/output/figure_pipeline/2015p2/q018-b2 was published as
a failed classification audit because the raw response contained four evidence
items and used subtype quadrilateral as a secondary tag. The strict parser
rejected it without coercion, retained the raw response and response SHA-256,
and preserved the B1 source/crop hash. A human-corrected response is required
before review publication.

Out of scope: B3 visible-label OCR, B4 structured figure/table analysis,
embeddings, Qdrant ingest and answer reasoning.
