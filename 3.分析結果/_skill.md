# 3.分析結果

## 目的

集中管理 OCR 輸出品質、coverage、人工檢查紀錄與修訂報告。原始 output
artifact 不應直接被分析腳本覆寫。

## 適用 skills

- `qa-only`：只分析及回報品質，不修改 production code。
- `systematic-debugging`：從錯誤樣本、overlay 與 logs 追查 root cause。
- `benchmark-models`：以固定 golden set 比較 OCR engine 表現。
- `code-review-skill`：檢查未使用、重複或過時 code；刪除前先取得使用者同意。

分析時保留原始 artifact，結論需指出檔案、題號或可重現證據；只在任務需要時載入相應 skill。

## 已分類檔案

- `error.txt`：使用者肉眼檢查後的 OCR 問題紀錄。
- `debug_output.txt`：診斷用執行記錄。
- `error_analysis.md`：歷史 error analysis 報告。
- `_reports/p-ocr-branch-scorecard.md`：OCR engine 評估 scorecard。
- `_reports/sdd/`：歷史 task reports、review packages、分析 JSON 與 logs。
- `_scripts/____validate_report.js`：報告／品質結果驗證入口模板。
- `_scripts/____revise_report.js`：依人工意見產生修訂副本的入口模板。

`output/` 是產線的 canonical artifact 目錄，為避免破壞 resume 與 handoff，仍
保留在 repository root。`findings.md`、`progress.md` 與 handoff 也保留在 root
作為目前專案狀態來源。

驗證與修訂應輸出到新的報告路徑，保留原始結果以便比較。
