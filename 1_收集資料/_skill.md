# 1_收集資料

## 目的

集中管理外部資料、PDF、原始圖片與清理前的資料。這一層不直接修改
`src/ocr_pipeline`，也不應覆寫原始來源檔案。

## 已分類檔案

- `_scripts/____collect_data.js`：收集資料的安全入口模板。
- `_scripts/____clean_data.js`：清理副本或暫存資料的安全入口模板。
- `_scripts/pdf_to_images.py`：將 PDF 轉成逐頁 PNG 的舊式輔助工具。
- 原始 PDF 與頁面圖片仍保留在 runtime 使用的 `data/sources/`、`data/pdf_pages/`。

執行前確認輸入與輸出路徑；預設使用 dry-run，避免意外覆寫或刪除。

## 適用 skills

- `browse`：搜尋及核對網上資料。
- `scrape`：擷取已選定網頁的內容。
- `pdf:pdf`：讀取或檢查 PDF 原始資料。
- `context7-mcp`：查詢 library、SDK、API 或 CLI 的最新官方文件。

只在任務需要時載入相應 skill；不要一次載入全部。

## 網上資料採用規則

完成網上查詢後，只有確認會採用的資料才寫入本資料夾。保存資料本體或摘要，並記錄：

- 原始來源 URL
- 查閱日期
- 資料用途／對應任務
- 必要的版本、發布日期或摘要

未採用的搜尋結果只留在對話脈絡，不寫入 repository。不可把 API key、token、cookie
或其他 secret 寫入資料夾或 commit。
