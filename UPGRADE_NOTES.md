# VLM / PDF 升級筆記（從 AIbuliding 抽出）

## 現況基線

- VLM：`zai-org/GLM-4.6V-Flash`（預設）+ 4bit（4070 Super 12GB）
- 備援：`zai-org/GLM-4.1V-9B-Base` / `zai-org/GLM-4.1V-9B-Thinking`
- 輸入：試卷 PDF（預設繁中 DSE）
- 輸出：`data/draft.jsonl`（chat messages 格式，與 LoRA JSONL 相容）
- 圖題策略：看圖 → `figure_description` 文字化 → 併入 `question`（訓練端仍是純文字）

## 已驗證過的問題

| 問題 | 狀態 |
|------|------|
| 缺 torchvision | 需安裝 CUDA 對應版 |
| `file://` + 中文路徑失敗 | 已改 PIL |
| YAML `256 * 28 * 28` 無法 int() | 已改數字 + 容錯 |
| 短題 (a)(b) 被拆成兩筆 | prompt 已要求合併 + `merge_draft_subparts.py` |
| 漏題幹（如「因式分解」） | 仍需人工審 |
| 指數／符號 OCR 錯 | 仍需人工審 |
| JSON 裡 LaTeX `\` 弄壞 parse | `fix_invalid_json_escapes` 已加 |

## 建議升級優先級

### P0 — 資料品質

1. 跳過 junk 頁（條碼、「寫於邊界以外」）在提取階段，不只在 `jsonl_to_latex --skip`  
2. 強制「一大題一筆」：同頁同號合併；缺題幹時用鄰近文字／版面啟發式補  
3. 抽樣對照原 PDF 圖做 QA checklist

### P1 — 模型／效能

1. 比對 `local`（GLM-4.6V-Flash）與 `local_41_base`（GLM-4.1V）抽題正確率  
2. 加 `--pages 3-10` / `--skip-pages 1,10`  
3. 批次抽題時快取模型，避免每跑一輪重載

### P2 — 產品化

1. 獨立 venv + 簡單 CLI：`pdfscan extract paper.pdf`  
2. 可選 API backend（品質／成本取捨）  
3. 匯出／匯入與 AIbuliding `train.jsonl` 的明確邊界（只拷貝 approved）

## 與 AIbuliding 的關係

- **本目錄**：專心升級掃描／VLM／draft 品質  
- **AIbuliding**：LoRA 訓練；需要資料時從這裡拷貝 `draft.jsonl` 或 promote 後的列  

兩邊腳本目前同源；升級後若要同步回 AIbuliding，再決定 merge 或 submodule。
