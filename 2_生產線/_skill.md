# 2_生產線

## 目的

管理 PDF → Stage1 layout → Stage2 OCR → deterministic Stage3 → TXT/TEX/
PageIR/questions.jsonl 的正式產線說明、輔助腳本與歷史設計資料。

## 目前正式 runtime

- 主力 Stage2：PaddleOCR-VL。
- 後備／公式：本機 Qwen3-VL 4-bit，使用 `--text-engine vlm` 明確選擇。
- Stage3：deterministic sanitize，不使用第二次 VLM rewrite。

## 適用 skills

- `systematic-debugging`：定位 OCR、layout、engine 或 pipeline 問題的 root cause。
- `modern-python`：小型重構、型別與 Python 3.12 程式品質檢查。
- `pytest-skill`：新增或修訂 focused tests。
- `context7-mcp`：涉及 library、SDK、API 或 CLI 時查最新官方文件。

修改流程：一次一個小改動，先說明涉及檔案；每步跑 focused pytest，通過後再繼續。

## 已分類檔案

- `current_ocr_pipeline_flow.txt`、`FIGURE_PIPELINE_HANDOFF.md`、
  `OCR_PIPELINE_DESIGN.md`：目前產線說明。
- `TODOS.md`：產線 backlog。
- `_handbooks/`：MCP、skill、homelab 與 Windows sandbox 操作文件。
- `_script/cleanup_glm_weights.ps1`：限定模型 cache 的維護工具，預設 dry-run。
- `_experiments/arabic_qwen35_ocr/`：隔離的 Arabic-Qwen3.5 OCR 實驗，不屬於 DSE trunk。
- `_archive/requirements-extract.txt`、`_archive/CLAUDE.md`：舊依賴與 agent 指令。
- `_history/plans/`、`_history/specs/`、`_history/sdd/`：歷史計畫、規格與 task briefs。

正式 runtime 仍位於 repository 的 `src/ocr_pipeline/`、`scripts/`、
`config/` 與 `run_ocr_pipeline.py`；不要為了分類而搬動這些路徑。正式測試仍
位於 `tests/`，輸出仍位於 `output/`。

`_script/` 保留給產線專用的一次性輔助腳本。只在任務需要時載入相應 skill。
