# Figure / Table Pipeline Handoff

## A. 專案背景

最終產品是可輸入圖片、截圖或 PDF 的數學 AI Chat，能解答及生成數學題。
JSONL 是可重建的主要資料來源；Qdrant 是可重建的搜尋索引。未來需要同時
支援 text retrieval 與 image retrieval。

目前分成兩條獨立產線：

- Track A：文字／數學公式 OCR。
- Track B：圖形／圖表／表格 OCR、描述、向量化與搜尋。

兩條產線不可直接改寫對方的結果，只能透過穩定 ID 與 schema 合併。

## B. 圖片線責任範圍

圖片線負責：

- 保存 figure/table crop、bbox、page、hash。
- `FigureAsset`／`TableAsset` schema。
- 圖片類型分類。
- 圖中的可見文字、字母、數字、角度、刻度與坐標軸標籤 OCR。
- 幾何圖、坐標圖、函數圖、統計圖表的結構化描述。
- 表格結構抽取及 validation。
- image embedding、caption embedding。
- Qdrant image vector ingest。
- 以 `parent_question_id` 連回題目。

圖片線不負責：

- 修改文字線的 `OcrSpan`、`McqSpanChoices`、`McqSpanOcrResult`。
- 修改固定五行 renderer 或 MCQ A–D 規則。
- 重做已有的題幹／公式 OCR。
- 把圖形描述插入 `rendered_text`。
- 自動更改題目或答案。
- 覆寫已人工驗證的文字內容。

### 需要文字 OCR 時：直接重用現有 Qwen3-VL

若圖片線只需要一般文字、公式或 visible labels OCR，不要重新選模型、建立
第二套文字 OCR，或再次要求使用者解釋流程。直接使用現有本地
`Qwen/Qwen3-VL-8B-Instruct` 4-bit 路徑：

- 設定：`2_生產線/config/ocr_pipeline.yaml`
- client：`2_生產線/src/ocr_pipeline/vlm_client.py::build_vlm_client`
- engine：`2_生產線/src/ocr_pipeline/engines/vlm_text.py::VlmTextEngine`
- routing：`2_生產線/src/ocr_pipeline/routers.py::TextRouter`
- prompts：`TEXT_ROUTER_PROMPT`／`MCQ_ROUTER_PROMPT`
- validation/render：`2_生產線/src/ocr_pipeline/mcq_structured.py`

完整 DSE Paper 2 優先使用現有 CLI，讓 Stage1 metadata、prompt routing、
Pydantic validation、fallback、TXT/TEX 與 JSONL 全部沿用既有邏輯：

```powershell
uv run python 2_生產線/run_ocr_pipeline.py 1_收集資料/data/sources/2023p2.pdf `
  --dse-mcq --reuse-layout --text-engine vlm `
  --crop-dir 3.分析結果/output/crops/2023p2-qwen-text `
  --output-tag qwen-text
```

執行前必須確認新的 `crop-dir` 與 output tag 不存在，避免覆寫。`vlm` 就是
目前鎖定的 Qwen3-VL，不是外部 API。`structured_ocr.enabled` 保持
`false`；不要建立 API key，也不要啟用 Instructor。

只有需要 OCR 單張 crop、而且不需要完整 pipeline artifacts 時，才直接
使用 engine。整批圖片只建立一個 client／engine，禁止每張圖重新載入模型：

```python
from pathlib import Path

from ocr_pipeline.engines.vlm_text import VlmTextEngine
from ocr_pipeline.factory import load_ocr_config
from ocr_pipeline.prompts import TEXT_ROUTER_PROMPT
from ocr_pipeline.vlm_client import build_vlm_client

config = load_ocr_config(Path("2_生產線/config/ocr_pipeline.yaml"))
client = build_vlm_client(config)
engine = VlmTextEngine(
    client,
    max_new_tokens=int(config["vlm"]["max_new_tokens_route"]),
)

text = engine.ocr(
    Path("path/to/crop.png"),
    prompt=TEXT_ROUTER_PROMPT,
)
```

若 crop 是完整 MCQ，應交給 `TextRouter` 並確保
`block.meta["question_id"]` 是 `int`；router 會自動使用
`MCQ_ROUTER_PROMPT`。題號必須來自 Stage1 metadata，不可要求 Qwen
重新辨識。不要直接複製 Qwen raw output 取代 renderer。

這個重用入口只處理文字／公式 OCR。幾何關係、函數圖意義、圖表資料及
答案推理仍屬圖片線，不得借用文字 prompt 猜測。

GPU 規則：

- 一次只能有一個 OCR pipeline 使用 12 GB GPU。
- 使用者要求可見執行時，不得啟動背景程序。
- 完成整批工作後讓程序正常結束以釋放 Qwen。

## C. 現有文字線輸出契約

```text
OcrSpan:
  kind: "text" | "math"
  content: str

McqSpanChoices:
  A: list[OcrSpan]
  B: list[OcrSpan]
  C: list[OcrSpan]
  D: list[OcrSpan]

McqSpanOcrResult:
  stem: list[OcrSpan]
  choices: McqSpanChoices
```

每題 rendered text 固定五行：

```text
N. 題幹
A. 選項 A
B. 選項 B
C. 選項 C
D. 選項 D
```

題號由 Stage1 `block.meta["question_id"]` 提供。模型不加入題號、A–D
標籤、`$...$` 或最終換行。

成功與 fallback 契約：

```text
structured JSON
→ parse_span_json()
→ structured_ocr_source = "local_span_json"
→ render_span_result()

若失敗：
→ parse_stage2_text()
→ structured_ocr_source = "local_stage2_fallback"
→ render_text()

兩者都失敗：
→ 保留原始 OCR
→ structured_ocr_source = "local_validation_failed"
→ 記錄 structured_ocr_error
```

不得移除 fallback、加入第二次 VLM formatting inference，或用 regex
猜測 text/math。圖片線不得更改以上契約。

## D. 圖片線建議分階段工作

### Phase B1：Asset preservation

- 不分析圖片。
- 保存原 crop、bbox、page、question_id、asset_id、SHA-256。
- 確保可由 JSONL 找回原圖。

### Phase B2：Asset classification

- `geometry`
- `coordinate_graph`
- `function_graph`
- `statistical_chart`
- `table`
- `physical_diagram`
- `illustration`
- `unknown`

### Phase B3：Visible label OCR

提取圖中字母、數字、角度、刻度、坐標軸標籤、圖例、表格文字及可見數學
符號。需要純文字 OCR 時使用上面的現有 Qwen3-VL 入口。

### Phase B4：Structured figure/table analysis

Figure 可輸出 `entities`、`relations`、`visible_labels`、`description`、
`confidence`。Table 可輸出 `rows`、`columns`、`cells`、`headers`、
merged-cell metadata 與 `confidence`。

### Phase B5：Embeddings

- question image embedding
- figure image embedding
- figure caption embedding
- table text embedding
- 每個向量保存 embedding model/version

### Phase B6：Qdrant ingest

- named image vectors
- caption vectors
- `parent_question_id`
- validation status
- asset metadata

## E. 圖片線建議 schema

最小 `FigureAsset` 草案：

```json
{
  "schema_version": "1.0",
  "asset_id": "hk-dse-2023-math-p2-q018-fig01",
  "parent_question_id": "hk-dse-2023-math-p2-q018",
  "asset_type": "figure",
  "figure_type": "unknown",
  "source": {
    "page": 5,
    "crop_path": "assets/2023p2/q018_fig01.png",
    "bbox": [0, 0, 0, 0],
    "sha256": "..."
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

最小 `TableAsset` 草案：

```json
{
  "schema_version": "1.0",
  "asset_id": "hk-dse-2023-math-p2-q020-table01",
  "parent_question_id": "hk-dse-2023-math-p2-q020",
  "asset_type": "table",
  "source": {
    "page": 6,
    "crop_path": "assets/2023p2/q020_table01.png",
    "bbox": [0, 0, 0, 0],
    "sha256": "..."
  },
  "headers": [],
  "rows": [],
  "cells": [],
  "rendered_markdown": null,
  "validation": {
    "status": "pending",
    "reviewed": false
  }
}
```

建立類別前先搜尋現有 models/schema，避免重複或衝突。

## F. 整合規則

文字線與圖片線由獨立 `QuestionAssembler` 合併：

```text
text_result.question_id == figure_result.parent_question_id
```

不得依賴陣列位置、檔名或檔案排序配對。共享欄位包括：

- `document_id`
- `question_id`
- `page`
- `source_pdf`
- `question_crop_path`
- `asset_id`
- `parent_question_id`
- `schema_version`
- `pipeline_version`

建議 ID：

```text
hk-dse-2023-math-p2-q001
hk-dse-2023-math-p2-q001-fig01
hk-dse-2023-math-p2-q001-table01
```

允許 partial：

```json
{
  "text_result": {"status": "complete"},
  "figure_result": {"status": "pending"},
  "validation": {"status": "partial"}
}
```

只有 schema、asset reference 與 validation 都通過後才能標記
`ready_for_ingest`。

## G. Qdrant 原則

- JSONL 是主要可重建資料來源；Qdrant 只是搜尋索引。
- 不把完整 Base64 圖片放入 Qdrant payload。
- 圖片保存在檔案系統、NAS 或 object storage。
- payload 只保存 path/URL、hash、metadata。
- 圖片描述修改後更新 caption embedding。
- 圖片本身修改後更新 image embedding。
- 每個 embedding 保存 model/version。
- 模型不得覆寫人工驗證資料。

## H. 圖片線驗收標準

第一個里程碑，同一道附圖題目可產生：

1. question crop
2. `text_result.json`
3. figure crop
4. `figure_asset.json`
5. 共享 `question_id`／`parent_question_id`
6. combined JSONL
7. 圖片尚未理解時仍不遺失
8. 不影響文字五行輸出

後續里程碑：

- 相同圖片、裁切或輕微縮放後仍可由 image embedding 找回原題。
- 圖形描述不捏造不存在的關係。
- 表格 row/column 不錯位。
- 圖片結果可獨立重新分析，不必重跑文字 OCR。

## I. 已知風險

- 圖形描述模型可能幻覺。
- 幾何關係不可只靠自然語言描述。
- 圖中文字 OCR 與圖形理解是不同任務。
- image embedding 與圖片描述也是不同任務。
- 同一題可能有多個 assets。
- table 不應與普通 text block 混為一談。
- asset 必須保留原圖與 hash。
- 不可依賴檔名排序建立父子關係。
- 不可將圖片分析塞進現有五行 renderer。

## 下一個圖片線 Agent 的第一個任務

只做 Phase B1：從一題附圖 MCQ 建立可追溯的 figure crop 與
`FigureAsset` JSON，包含 bbox、page、question_id、asset_id、SHA-256；
先不要加入 embedding、Qdrant collection 或圖形理解。

## Figure Track — Phase B2 status (2026-08-02; review updated 2026-08-04)

Phase B2 is implemented as an isolated semantic-classification boundary after
MinerU layout/detection and B1 asset preservation:

1. classification_runner validates the B1 JSON and crop SHA-256.
2. One local Qwen3-VL 8B 4-bit client classifies each crop sequentially.
3. The strict parser accepts only the six-field JSON contract and records failed
   raw responses instead of guessing.
4. classification_review publishes approved, corrected or rejected decisions
   to a new bundle; failed audits may be corrected or rejected using their
   recorded prompt version as the source-attempt ID, while approval still
   requires a parsed proposal. It never mutates B1.
5. phase_b2_figure_classify.py exposes separate propose and review commands.
   Review does not load a model.

The recorded-response Q18 acceptance passed with identity, bbox, source/crop
hash and immutable-source checks. The real local Qwen smoke also published a
valid failure audit at 3.分析結果/output/figure_pipeline/2015p2/q018-b2: the model
returned four evidence items and a subtype in secondary_tags, so strict
validation intentionally kept figure_type=unknown and
classification.reviewed=null. The raw response and SHA-256 are retained for
diagnosis. On 2026-08-04, the Figure agent visually reviewed the crop and
published a corrected review at
`3.分析結果/output/figure_pipeline/2015p2/q018-b2-reviewed`:
`figure_type=geometry`, reviewed `subtype=triangle`, and no secondary tags.
The original failed B2 bundle remains immutable; the question crop, figure
crop and raw-response SHA-256 values were preserved in the reviewed copy.

The next permitted figure work is Phase B3 visible-label OCR. B4 structured
analysis, embeddings and Qdrant ingest remain out of scope for this handoff.

## Figure Track — Phase B3 status (2026-08-05)

Phase B3 visible-label OCR is implemented as a separate stage after a valid B2
bundle. It does not mutate B1 or B2 and does not perform structured geometry
reasoning, embeddings, retrieval or answer generation.

1. `label_ocr_runner` validates the B2 JSON, figure-crop SHA-256 and any B2
   classification raw-response reference before inference.
2. The existing local `Qwen/Qwen3-VL-8B-Instruct` 4-bit client transcribes only
   labels visibly printed in the figure crop. The prompt forbids solving,
   description and inferred geometric relations.
3. The strict parser accepts only `labels`, `confidence` and
   `needs_review=true`. B3 artifacts use `schema_version=1.2` and
   `pipeline_version=figure-b3-v1`.
4. Every valid proposal remains pending until an explicit approved, corrected
   or rejected review publishes a new sibling bundle. Failed raw responses are
   retained with their SHA-256 and may only be corrected or rejected.
5. `phase_b3_visible_labels.py` exposes separate `propose` and `review`
   commands. Review never loads the model.

Verification is green: the B3 targeted suite is `50 passed`, the full Figure
pipeline suite is `156 passed`, and Ruff reports no errors. After the
text-track GPU worker exited, the real local Qwen smoke published a pending
proposal at `3.分析結果/output/figure_pipeline/2015p2/q018-b3`. Qwen found all
six labels but returned them in `A, B, C, D, α, β` order with confidence `0.0`.
Visual review therefore published a corrected sibling at
`3.分析結果/output/figure_pipeline/2015p2/q018-b3-reviewed` with natural order
`B, β, C, A, α, D`. The pending source remains unchanged. Question, crop and
B2 raw-response SHA-256 values are identical across the B2 input, pending B3
and reviewed B3 bundles.

The next permitted figure work is a separately designed Phase B4 structured
figure/table analysis. Embeddings, Qdrant ingest and answer reasoning remain
out of scope.

## Figure Track — Phase B3 multi-shape benchmark (2026-08-05)

Before starting B4, six additional source crops were run through manual B1
figure isolation, B2 classification and real local B3 Qwen OCR:

- 2012 Q16 sector/annular arc;
- 2012 Q20 circle and cyclic quadrilateral;
- 2013 Q16 semicircle with shaded segment;
- 2013 Q20 bearing diagram with compass labels;
- 2014 Q16 square with an external triangle;
- 2021 Q20 square with intersecting triangles.

The reproducible manifest and report are
`3.分析結果/output/figure_pipeline/benchmark/benchmark-manifest.json` and
`3.分析結果/reports/figure_pipeline/b3_visible_label_benchmark_2026-08-05.md`.
All six B3 proposals parsed successfully and found the complete text label
multiset. Five were approved unchanged; 2013 Q20 was corrected because the
Chinese compass labels `北` and `東` must use `kind=axis_label`, not generic
`text`. The measured `(text, kind)` micro precision/recall is `94.1%` (32/34);
proposal confidence is not calibrated because two correct proposals reported
`0.0`.

The B3 prompt iteration is now recorded below. Do not begin embeddings or
Qdrant ingest from the exploratory predictions.

## Figure Track — Phase B3 prompt v2/v3 iteration (2026-08-05)

Prompt versioning is now separate from the stable artifact shape. B3 assets
remain `schema_version=1.2` and `pipeline_version=figure-b3-v1`; proposal and
failed-audit metadata accept `figure-b3-v1`, `figure-b3-v2` and
`figure-b3-v3`. The config default is v3, while v1 and v2 remain reproducible.

The same six reviewed B2 inputs were rerun without changing their crops:

- v1 baseline: 6/6 parseable, 5/6 exact `(text, kind)`, micro F1 94.1%;
- v2: 5/6 parseable and exact, micro F1 88.5%; it fixed compass kinds but
  2014 Q16 degenerated into 384 exclamation marks;
- v3: 6/6 parseable and exact, 34 TP / 0 FP / 0 FN, micro F1 100%, with all six
  proposals approved unchanged after human comparison to the existing gold.

v3 removes v2's local `value or marker` adjacency wording, retains explicit
`北`/`東` axis-label and visual scan-order guidance, and defines confidence over
the complete transcription. All v3 proposals reported 0.95; this six-sample
all-correct result is not enough to claim broad confidence calibration. Order
is still excluded from the primary accuracy gate.

Verification is green: B3 targeted `59 passed`, full Figure pipeline
`171 passed`, and Ruff clean. All recomputed crop hashes match their metadata
across v1/v2/v3 pending and reviewed bundles. See
`3.分析結果/reports/figure_pipeline/b3_visible_label_benchmark_2026-08-05.md`
and `3.分析結果/output/figure_pipeline/benchmark/b3-prompt-comparison.json`.

The next permitted work is a wider, more varied holdout plus a separate
sequence-order metric. If that remains green, design Phase B4 structured
figure/table analysis. Embeddings, Qdrant ingest and answer reasoning remain
out of scope until their own contracts are approved.

## Figure Track — Expanded B3-v3 holdout (2026-08-07)

The wider holdout requested for the Figure line is complete. It adds six
manually isolated B1 bundles:

- 2018 Q6 coordinate graph with two labelled lines;
- 2018 Q16 parallelogram with diagonals and vertices A–F;
- 2018 Q32 logarithmic function graph;
- 2022 Q14 non-geometry dot-pattern sequence;
- 2022 Q19 triangle with an exterior-angle construction;
- 2022 Q24 coordinate graph with a straight line.

The expanded manifest is
`3.分析結果/output/figure_pipeline/benchmark/benchmark-manifest-v2.json`.
The six B1 crops were passed to one sequential local
`Qwen/Qwen3-VL-8B-Instruct` 4-bit client for B2 and B3-v3, and every stage
was published as a new sibling bundle. The machine-readable result is
`3.分析結果/output/figure_pipeline/benchmark/holdout-comparison-2026-08-07.json`;
the narrative report is
`3.分析結果/reports/figure_pipeline/b3_visible_label_holdout_2026-08-07.md`.

B2 produced five parseable proposals and one strict failure audit. The failed
2018 Q16 response used `secondary_tags=["triangle"]` for a geometry proposal
and returned four evidence items; the raw response remains preserved. Human
review corrected it to `geometry/quadrilateral`; the other five B2 decisions
were approved. B3-v3 produced six parseable proposals, all six were approved
unchanged after visual inspection, and the new holdout scored 28 TP / 0 FP /
0 FN across typed label multisets (6/6 text-exact and 6/6 exact `(text, kind)`).
The combined twelve-sample result is 62 TP / 0 FP / 0 FN, 12/12 parseable and
100% micro precision/recall/F1. All proposals reported confidence `0.95`; this
is not evidence of general calibration. The dot-pattern sample has no printed
labels, so its valid result is an empty-label proposal and contributes no
positive label count.

The 30 new bundles (B1, B2, reviewed B2, B3-v3 and reviewed B3-v3) passed
schema validation and recomputed figure-crop SHA-256 checks. No source bundle
was overwritten. Per the current user instruction, sequence-order accuracy is
not defined or scored in this holdout; only text and `(text, kind)` multisets
are reported. The next Figure decision is therefore whether to proceed to a
separately scoped B4 structured figure/table contract, not to infer an order
metric from these results. Embeddings, Qdrant ingest and answer reasoning
remain out of scope.

## Figure Track — Separate B3 sequence-order metric (2026-08-07)

Sequence order now has an independent evaluation contract. Do not use the
ordered label list in the prior reviewed B3 bundles as gold: those reviews were
performed when order was explicitly outside the acceptance condition.

The `visual-scan-order-v1` gold is stored at
`3.分析結果/evals/figure_pipeline/b3_sequence_order_gold_v1.json` and binds each
annotation to `asset_id` and figure-crop SHA-256. The annotation policy scans
top-to-bottom by visual band and left-to-right inside a band; point labels use
their labelled point as the anchor. Alphabetical, geometry-traversal and
semantic grouping are not accepted as scan order.

The primary `occurrence-pairwise-v1` metric is micro Pairwise Order Accuracy.
It only scores samples whose predicted and gold typed label multisets match;
repeated labels receive stable occurrence indices. Samples with fewer than two
labels are trivial and contribute no pair. Exact Sequence Rate, macro Pairwise
Order Accuracy and macro LCS ratio are also reported.

Current B3-v3 result on the twelve-sample benchmark: 12/12 content-matched, 11
nontrivial, exact sequence `3/11 = 27.3%`, micro Pairwise Order Accuracy
`100/156 = 64.1%`, macro Pairwise Order Accuracy `64.8%`, and macro LCS ratio
`69.4%`. Thus the existing 100% label-content F1 must not be interpreted as
correct reading order.

Implementation:
`2_生產線/src/figure_pipeline/sequence_order_metrics.py`,
`sequence_order_evaluator.py`, `sequence_order_cli.py`, and
`2_生產線/_script/evaluate_b3_sequence_order.py`. Definition and report:
`3.分析結果/docs/figure_pipeline/sequence_order_metric_v1.md` and
`3.分析結果/reports/figure_pipeline/b3_sequence_order_evaluation_2026-08-07.md`.
Machine output:
`3.分析結果/output/figure_pipeline/benchmark/b3-sequence-order-v1.json`.

No B3 prompt or reviewed bundle was changed. Before making this a release
threshold, add a second independent annotation and measure row-grouping
agreement. Full Figure suite: `183 passed`; Ruff clean. B4, embeddings, Qdrant
ingest and answer reasoning remain separate future scopes.
