# MCP 使用手冊（PC-A Cursor）

更新日期：2026-07-23  
設定檔：`~/.cursor/mcp.json`  
規則：`.cursor/rules/tool-routing.mdc`（Skill＋MCP 混合）

## 怎麼用好

1. 開 **Agent**（不是純 Ask）。
2. 講任務，不必每次喊 MCP 名；規則會導向。
3. 關鍵任務可點名，例如：「用 context7 查 Qdrant upsert」。
4. 新裝／剛綠燈 → **新開對話**。
5. 工具太多易選錯 → Settings → MCP 關掉少用的 tool。
6. 紅燈：說一聲，改用本機備援（`gh`、檔案、Shell）。

## 禁忌

- 題庫／記憶：**只用 B 上 Qdrant**，勿再加 Chroma／Cognee／Mengram。
- `Z:\jobs`：勿繞過 `DONE.json`／publish 亂寫。
- MCP `qdrant` = **唯讀**；寫入走 A 上 `homelab/ingest`。
- 密鑰勿貼進 chat／commit。

---

## 伺服器一覽

| MCP | 一句話 | 何時用 | 前置 |
|-----|--------|--------|------|
| **qdrant** | 查 B 機向量庫（唯讀） | 題庫／memories 語意搜 | B Qdrant 開著；預設 collection=`memories`（題庫多半是 `exam_segments_v1`，查題庫時講清 collection） |
| **zero-api-key-web-search** | 搜網＋讀頁＋查證 | 最新資訊、驗說法、抓 URL | 無（預設免 key） |
| **context7** | 套件／框架最新文件 | 「這個 API 怎麼用」 | 有 key 較穩 |
| **codebase-memory** | 程式碼知識圖 | 誰呼叫誰、架構、跨檔關係 | 先 `index` 專案一次 |
| **github** | GitHub API（issue／PR／搜碼） | 開 PR、看 issue、遠端碼 | 環境變數 `GITHUB_PERSONAL_ACCESS_TOKEN` |
| **filesystem** | 限定目錄讀寫 | 本專案、`aiworkplace`、`Z:\` | 根目錄已鎖死這三個 |
| **gpu** | NVIDIA 利用率／VRAM | OCR／VLM 前看顯存 | Docker Desktop + GPU |
| **arxiv-latex** | arXiv 論文 LaTeX 原文 | 公式／章節精讀 | 網通；給 arXiv id |
| **zotero** | 個人文獻庫 | 搜收藏、引用、筆記 | Zotero 開著＋允許本機 API |

---

## 任務速查

| 你想… | 用 |
|-------|-----|
| 套件文件 | context7 |
| 搜網／證實 | zero-api-key-web-search |
| 本 repo 結構／呼叫鏈 | codebase-memory |
| GitHub PR／issue | github |
| Samba／jobs 檔 | filesystem（守 DONE 契約） |
| 向量搜尋 | qdrant |
| VRAM | gpu |
| 論文方程式 | arxiv-latex |
| 我的論文庫 | zotero |

---

## 各伺服器備註

### qdrant
- URL：`http://192.168.1.107:6333`（LAN）
- MCP 唯讀。寫入：`homelab/ingest` + writer key（在 B `.env`）。
- 題庫 collection：`exam_segments_v1`（Wave 1）。MCP 預設 `memories` ≠ 題庫。

### zero-api-key-web-search
- 工具大概：搜尋、llm_context、browse、verify、evidence_report。
- 比「猜訓練資料」準；需要證據時優先。

### context7
- 流程：resolve library id → query-docs。
- Prompt 可寫：`use library /org/pkg`。

### codebase-memory
- 本機 binary；先 index 再查。
- 管**程式結構**，不管題庫向量。

### github
- 遠端 MCP。PAT 用環境變數，重開 Cursor。
- 小操作也可用 `gh` CLI 備援。

### filesystem
- 允許：`pdf scaner`、`aiworkplace`、`Z:\`。
- 寫 jobs 必須走 publish／DONE 流程。

### gpu
- Docker：`ghcr.io/pmady/gpu-mcp-server`。
- OCR 前看 free VRAM；Surya 沒 release 會佔滿。

### arxiv-latex
- 給 id（如 `2401.12345`）拿 LaTeX／章節；數學比 HTML 準。

### zotero
- `ZOTERO_LOCAL=true`。Zotero 關閉 = 工具失敗。

---

## 故障快修

| 現象 | 做 |
|------|-----|
| 綠燈但 Agent 不用 | 新對話；Settings 裡 toggle MCP 一次 |
| github 紅 | 設 PAT 後重開 Cursor |
| zotero 紅 | 開 Zotero + Advanced 允許本機通訊 |
| gpu 紅 | 開 Docker；確認 `--gpus` 可用 |
| qdrant 空結果 | 確認 collection 名；題庫用 `exam_segments_v1` |

---

## 與產品邊界

```
OCR（A）→ publish → B jobs + DONE
       → ingest（A writer）→ Qdrant exam_segments_v1
Cursor MCP qdrant = 讀
將來老師 Chat = 讀 B，不寫向量
```

詳見：`homelab/DATA_PLANE.md`、`handoff.md`。
