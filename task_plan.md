# Task Plan: PDF Scaner — OCR 管線穩定化 + Qdrant 題庫檢索

## Goal
把本專案做成可重複執行的「PDF → 可編輯 LaTeX 草稿 → 編譯 PDF（教師 reuse）」流程；Qdrant 為並行／後續能力。

對齊：
- Design: `~/.gstack/projects/pdf-scaner/a1217-main-design-20260721-101300.md`
- Eng+DX plan: `~/.gstack/projects/pdf-scaner/a1217-main-eng-review-plan-20260721.md`
- Architecture: `%TEMP%/architecture-review-20260721-pdf-scaner.html`

## Current Phase
**Phase 2.5b** next — LayoutArtifact；或依需要先手編更多頁驗證

## Hardware / model (locked from architecture review)

| Item | Decision |
|------|----------|
| GPU | RTX 4070 Super **12GB** |
| Default VLM | **Qwen2.5-VL-7B-Instruct 4bit**（非 GLM-Flash；非先上 8bit） |
| GLM-4.6V-Flash | 可選 adapter，非預設 |
| Surya | 優先 Docker/vLLM，避免與 VLM 搶同卡 |
| Order | Sanitize → VlmClient/Qwen → LayoutArtifact → MinerU |

## Tooling

| When | Invoke |
|------|--------|
| Plan lock | `/plan-eng-review`（已做）+ 本 design-review 修訂 |
| Bugs | `/investigate` |
| Diff | `/review` |
| Golden | `/qa` + `xelatex`/`latexmk` |
| Visual | `cursor-ide-browser` |
| Memory | `user-qdrant` |

## Phases

### Phase 1: 環境 — complete

### Phase 2: 盤點 — mostly complete

### Phase 2.5a: Compile-friendly + lighter VLM — **NOW**
- [x] T1 `sanitize_tex_document`（tabular-aware）
- [x] T2 polish_per_page 雙 preamble 修復
- [x] T3 prompts/config/DESIGN 對齊 delimiter 政策
- [x] T7 VlmClient seam + 預設 Qwen 7B 4bit（code；GPU smoke pending）
- [x] T4 pytest unit suite（sanitize / merge / vlm factory）— TeX smoke optional later
- [x] T5 共用 exit helper（DR1–DR9：成功塊／preflight／exit／單行 WARN）
- [x] T6 README 教師旅程 + 狀態表 + golden + Stage3 靜默說明
- [x] Golden accept（pipeline exit 0；提取 fence；小改後 latexmk → PDF）
- **Status:** complete (2.5a code + golden)

### Phase 2.5b: LayoutArtifact（resume seam）
- [ ] T8 持久化 LayoutBlock JSON；可只重跑 route/polish
- **Status:** pending（after 2.5a）

### Phase 3: Qdrant — optional-parallel（不擋 2.5a）

### Phase 4: MinerU adapter + Approach B templates
- [ ] 真 MinerU（證據：公式內容錯，非 delimiter）
- [ ] Approach B 入場條件達標後模板化
- **Status:** pending

### Phase 5: 訓練銜接 — pending

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Qwen 7B 4bit 預設 | 12GB 上 GLM-Flash 吃力；草稿夠用 |
| Sanitize before MinerU | 可編譯工作稿 > 換公式引擎 |
| 無 App UI；CLI DX = eng plan DR1–DR9 | Design review complete |
| `--check-compile` defer | Eng D5-C |
| 無 `.warn.log` | Design D12-B |

## Next Action
Phase 2.5a 完成。最近一次 run exit 0；tabular `{…\\…}` 已加 sanitizer。
