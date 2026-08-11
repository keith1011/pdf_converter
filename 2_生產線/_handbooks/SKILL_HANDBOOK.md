# Skill 使用手冊（PC-A Cursor）

更新日期：2026-07-23  
位置：`~/.cursor/skills/`（另有 `~/.agents/skills/`、`~/.cursor/skills-cursor/`）  
專案規則：`.cursor/rules/planning-with-files.mdc`、`tool-routing.mdc`（Skill＋MCP）

## 怎麼用好

1. **Agent** 對話；任務對上 description 才會自動選。
2. 不準 → **點名**：`用 systematic-debugging`、`/gstack-office-hours`、`/caveman lite`。
3. Skill = 工作流／手冊；MCP = 外接工具。可並用（例：investigate + gpu MCP）。
4. 裝太多會搶注意力 → 日常只記下面「常用表」；其餘用時再喊。
5. 新 skill → **新開對話**。
6. 寫 code／commit／PR 內容：照 skill 規定正常寫；回覆語氣才受 caveman 影響。

## 禁忌

- 非瑣事：必碰 `task_plan.md` / `findings.md` / `progress.md`（planning-with-files）。
- 勿同時開一堆互相打架的「記憶／向量」skill＋第二套向量庫。
- `caveman-compress` 會改檔 → 先確認再跑（風險較高）。

---

## 任務速查（先看這）

| 你想… | 用 |
|-------|-----|
| 記進度／決策／錯誤 | **planning-with-files**（always） |
| 產品／雙機架構腦暴 | **gstack-office-hours** |
| Bug／CUDA／測掛 | **systematic-debugging** → **gstack-investigate** |
| OCR 前後看 VRAM | MCP **gpu**（非 skill） |
| 套件文件 | MCP **context7** |
| 寫／查 PDF | **pdf** |
| 補 pytest | **pytest-skill** |
| uv／ruff／現代 Python | **modern-python** |
| 密鑰／.env 安全 | **varlock**、**insecure-defaults** |
| 自建 MCP | **mcp-builder** |
| 題庫檢索品質 | **qdrant-search-quality**、**evaluate-rag** |
| Eval／失敗分析 | **error-analysis**、**eval-audit**、**generate-synthetic-data** |
| HF 資料／微調 | **huggingface-***、**trl-training** |
| 架構／領域模型 | **codebase-design**、**domain-modeling**、**improve-codebase-architecture** |
| 短回覆省 token | **caveman**（建議日常 **lite**） |
| 短 commit／短 review | **caveman-commit**、**caveman-review** |
| 設計拍板後實作計畫 | **gstack-autoplan** → **gstack-plan-eng-review** |
| 發版／PR | **gstack-ship**、**gstack-review** |
| QA 點瀏覽器 | **gstack-qa**、**gstack-browse** |

---

## 一、專案常駐

| Skill / 規則 | 功用 |
|--------------|------|
| **planning-with-files** | 檔案當工作記憶；2-action 寫 findings／progress；錯記入 Errors 表 |
| **tool-routing**（rule） | 任務域 → Skill＋MCP 組合 |

---

## 二、新裝（P0＋點名）

| Skill | 一句話 | 觸發例 |
|-------|--------|--------|
| **pdf** | 讀／合併／OCR／填表 PDF | 「處理這個 PDF」 |
| **mcp-builder** | 設計實作 MCP server | 「做一個 MCP」 |
| **modern-python** | uv、ruff、pytest 慣例 | 「整理 Python 專案」 |
| **insecure-defaults** | 掃硬編碼密鑰／弱預設 | 「安全掃一下」 |
| **varlock** | 密鑰不進 log／上下文 | 「管 .env／API key」 |
| **systematic-debugging** | 先找根因再修 | 「這個 bug」 |
| **pytest-skill** | 正規 pytest／fixtures | 「寫測試」 |

---

## 三、Caveman（回覆壓縮）

| Skill | 功用 |
|-------|------|
| **caveman** | 壓縮說話。級別：`lite`／`full`／`ultra`／`wenyan-*` |
| **caveman-commit** | 短 commit message |
| **caveman-review** | 短 PR 評語 |
| **caveman-compress** | 壓縮 memory 檔（慎用） |
| **caveman-help** | 指令速查 |
| **caveman-stats** | token 統計（偏 Claude Code log） |
| **cavecrew** | 委派 investigator／builder／reviewer |

建議日常：**lite**。關：`stop caveman`／`normal mode`。

---

## 四、題庫／RAG／Eval（研究線）

| Skill | 功用 |
|-------|------|
| **qdrant-search-quality** | Qdrant 檢索策略／診斷／hybrid |
| **qdrant-version-upgrade** | Qdrant 升級 |
| **evaluate-rag** | RAG 檢索＋生成評測 |
| **eval-audit** | Eval 管線健檢 |
| **error-analysis** | 失敗模式分類 |
| **generate-synthetic-data** | 合成測資 |
| **write-judge-prompt** | LLM-as-Judge prompt |

對齊：B = `exam_segments_v1`；MCP qdrant 唯讀。

---

## 五、HF／訓練（後續老師模型）

| Skill | 功用 |
|-------|------|
| **huggingface-datasets** | 資料集 |
| **huggingface-llm-trainer** | SFT 等訓練 |
| **huggingface-community-evals** | 社群評測 |
| **trl-training** | TRL 訓練流 |

現階段 OCR／資料平面優先；訓練 skill 備著。

---

## 六、工程設計（Matt Pocock 系）

| Skill | 功用 |
|-------|------|
| **setup-matt-pocock-skills** | 首次設定 issue tracker／domain 文檔 |
| **codebase-design** | 架構設計兩次再選 |
| **domain-modeling** | CONTEXT／ADR |
| **improve-codebase-architecture** | 重構架構 |
| **code-review** | 程式審查 |
| **grill-me**／**grilling** | 逼問需求／假設 |

---

## 七、gstack（常用子集）

全家桶很大；日常夠用這些：

| Skill | 功用 |
|-------|------|
| **gstack-office-hours** | 產品／架構面談 → 設計文 |
| **gstack-autoplan** | 實作計畫 |
| **gstack-plan-eng-review** | 工程審計畫 |
| **gstack-plan-ceo-review** | 商業／優先級審 |
| **gstack-investigate** | 系統性查 bug |
| **gstack-review**／**gstack-cso** | 碼審／安全 |
| **gstack-ship** | 測試＋PR |
| **gstack-qa**／**gstack-browse** | 瀏覽器 QA |
| **gstack-document-generate**／**release** | 文件 |
| **gstack-freeze**／**unfreeze** | 凍結範圍 |
| **gstack-retro**／**learn** | 復盤／學習 |
| **gstack-ios-*** | iOS（本專案少用） |

斜線指令多半：`/gstack-<名>`（以你 Cursor 實際註冊為準）。

---

## 八、Cursor 本體（`skills-cursor`）

| Skill | 功用 |
|-------|------|
| **create-rule**／**create-skill** | 寫規則／skill |
| **create-hook**／**create-subagent** | hook／子代理 |
| **update-cursor-settings** | 改 settings.json |
| **canvas** | 數據／分析 Canvas |
| **babysit**／**automate**／**loop** | 監 PR／自動化 |
| **review**／**review-security**／**review-bugbot** | 審查類 |
| **split-to-prs** | 拆 PR |

---

## 與 MCP 怎麼配

| 層 | 例子 |
|----|------|
| Skill 定流程 | systematic-debugging：先假設→證據→修 |
| MCP 取外訊 | gpu 看 VRAM；context7 查 API；qdrant 搜題庫 |
| Rule 綁習慣 | planning-with-files、mcp-routing |

詳見：`2_生產線/_handbooks/MCP_HANDBOOK.md`。

---

## 故障

| 現象 | 做 |
|------|-----|
| Agent 不讀 skill | 新對話；提示裡點名 skill 名 |
| gstack 指令沒反應 | 確認 skill 在 `~/.cursor/skills`；重開 Cursor |
| caveman 太難讀 | `/caveman lite` 或 `normal mode` |
| 選錯 skill | 一句話縮小任務＋點名正確那個 |

---

## 本專案建議日常組合

```
常駐: planning-with-files + mcp-routing
OCR/除錯: systematic-debugging + modern-python + pytest-skill + (MCP gpu)
資料平面: qdrant-search-quality + evaluate-rag
文件/PDF: pdf
安全: varlock + insecure-defaults
省 token: caveman lite（可選）
大決策: gstack-office-hours → autoplan
```
