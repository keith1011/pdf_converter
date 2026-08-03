# Error Analysis — pdf_converter OCR

## Corpus (Step 1)

| Source | Traces | Notes |
|--------|--------|-------|
| `golden_run_full2.log` + `3.分析結果/output/123.tex` + `1_收集資料/data/pdf_pages/123/page_*.png` | **14 page-level** | One full marking-scheme PDF |
| Target | ~100 | Need more PDFs / synthetic pages later |

**Trace unit:** one source PDF page → layout blocks → Stage2 routes → Stage3 polish slice → merged `.tex` region.

**Judgment criteria (teacher):** after ≤10 min edit, does this page’s TeX compile and look reusable vs hand-typed mark scheme?

Do **not** invent categories yet — pass/fail + notes first.

## Review log (Step 2)

| Trace ID | Input | Intermediate (first issues) | Output snippet | What went wrong (first) | Pass/Fail |
|----------|-------|----------------------------|----------------|-------------------------|-----------|
| 001 | page_001.png; layout 3 blocks (title, table, other) | WARN polish parse partial; auto polish_per_page | longtable Q1–3; then Chinese “以下是將圖片…” | - | Pass |
| 002 | page_002.png; layout 2 blocks (table, other) | Stage2 2 routes; polish parse partial (run-level) | Chinese meta + two tabulars (Q5 then Q4); marks cols empty | 整份 marking 根本沒有圖畫，輸出產生「有圖／轉圖」錯覺 | Fail |
| 003 | page_003.png; layout 2 blocks (table, other) | Stage2 2 routes | Chinese meta + Q6/Q7 tabular; math mostly OK; marks sparse | 同 002：無圖卻寫「將圖片…轉換」；算式抽取相對成功 | Fail |
| 004 | page_004.png; layout 2 blocks (table, other) | Stage2 2 routes | Q8 angles + Q9 sector in one tabular; marks cols empty; no 圖片 meta on this slice | - | Pass |
| 005 | page_005.png; layout 2 blocks (table, other) | Stage2 2 routes | Q10/Q11 tabular; has 圖片 meta; `=\alpha` vs \$14600 | - | Pass |
| 006 | page_006.png; layout 2 blocks (table, other) | Stage2 2 routes | Q12 stats tabular; marks misaligned; 简繁混 | - | Pass |
| 007 | page_007.png; layout 2 blocks (table, other) | Stage2 2 routes | Q13 congruence tabular; has 圖片 meta; one missing minus in angle line | - | Pass |
| 008 | page_008.png; layout 2 blocks (table, other) | Stage2 2 routes | Q14(a) L/circle; Markdown 圖片 meta; midpoint (-5,1); cols scrambled | 輸出 PDF 沒有隔行，部分內容看不到 | Fail |
| 009 | page_009.png; layout 2 blocks (table, other) | Stage2 2 routes | Q14(b) diameter; whole methods in one cell; 圖片 meta | 同上：無隔行，PDF 部分看不到 | Fail |
| 010 | page_010.png; layout 2 blocks (table, other) | Stage2 2 routes | Q15/Q16; 圖片 meta; cols scrambled; missing final fractions | - | Pass |
| 011 | page_011.png; layout 2 blocks (table, other) | Stage2 2 routes | Q17 sum/log; 圖片 meta; method2 exponents garbled | PDF 排版遮擋部分內容 | Fail |
| 012 | page_012.png; layout 2 blocks (table, other) | Stage2 2 routes | Q18 parabola; 圖片 meta; cols scrambled; `2^2 f(x)` | - | Pass |
| 013 | page_013.png; layout 2 blocks (table, other) | Stage2 2 routes | Q19 trig/area; 圖片 meta; sine denom wrong; has line breaks | - | Pass |
| 014 | page_014.png; layout 2 blocks (table, other) | Stage2 2 routes | pyramid volume; `p{12cm}`+`\\`; nested paren mess; BM² typo | - | Pass |

## Running tally (corpus A: 123.pdf, n=14)

| Pass | Fail | Fail rate |
|------|------|-----------|
| 9 | 5 | 5/14 ≈ 36% |

**Fail notes (raw — not categories yet):**
1. 002 — 整份 marking 根本沒有圖畫，輸出產生「有圖／轉圖」錯覺
2. 003 — 同 002；算式抽取相對成功
3. 008 — 輸出 PDF 沒有隔行，部分內容看不到
4. 009 — 同上：無隔行，PDF 部分看不到
5. 011 — PDF 排版遮擋部分內容

## Categories (Step 3) — locked for corpus A

| ID | Name | Definition |
|----|------|------------|
| C1 | 偽圖／轉圖 meta | 輸出含「將圖片…轉換為…」類說明；原 marking 頁無圖畫 |
| C2 | 缺隔行致不可見 | 解法擠成單格／無換行，PDF 部分內容看不到 |
| C3 | 排版遮擋 | 有一定換行，但排版（重疊／欄擠／高格）仍遮住內容 |

C2 與 C3 分開：根因不同（沒斷行 vs 斷行後仍遮擋）。  
C1 採**症狀是否出現**標註（即使該頁整體 Pass 也標 1）——因修 prompt／strip 時需知真實頻率。

## Labels (Step 4) — binary per category

| Trace | Overall | C1 meta | C2 無隔行 | C3 遮擋 |
|-------|---------|---------|-----------|---------|
| 001 | Pass | 1 | 0 | 0 |
| 002 | Fail | 1 | 0 | 0 |
| 003 | Fail | 1 | 0 | 0 |
| 004 | Pass | 0 | 0 | 0 |
| 005 | Pass | 1 | 0 | 0 |
| 006 | Pass | 0 | 0 | 0 |
| 007 | Pass | 1 | 0 | 0 |
| 008 | Fail | 1 | 1 | 0 |
| 009 | Fail | 1 | 1 | 0 |
| 010 | Pass | 1 | 0 | 0 |
| 011 | Fail | 1 | 0 | 1 |
| 012 | Pass | 1 | 0 | 0 |
| 013 | Pass | 1 | 0 | 0 |
| 014 | Pass | 0 | 0 | 0 |

C1 依據：`3.分析結果/output/123.tex` 該頁切片是否含「將圖片…」／Markdown 變體。  
C2／C3 依據：你的 Fail 第一因（008–009／011）。

## Failure rates (Step 5)

| Category | Rate | Count |
|----------|------|-------|
| **C1 偽圖／轉圖 meta** | **71%** | 10/14 |
| **C2 缺隔行致不可見** | **14%** | 2/14 |
| **C3 排版遮擋** | **7%** | 1/14 |

優先順序（頻率）：C1 ≫ C2 > C3。  
整體 Fail（第一因）仍是 5/14；C1 高頻但常不單獨導致整體 Fail。

## Decide fixes (Step 6) — draft

| Cat | Just fix? | Suggested action | Evaluator? |
|-----|-----------|------------------|------------|
| C1 | **Yes** | Prompt：禁止轉換說明／開場白；後處理 strip `以下是將…結果：` | 便宜：regex 檢測殘留 meta |
| C2 | **Yes** | Prompt：每步一行／`\\`；tabular 用 `p{…}`；禁止單格長文 | 可檢測：單 cell 字元數／無 `\\` |
| C3 | Later | 與 C2 同源加強；`\arraystretch`、欄寬、避免巢狀括號炸排版 | 先修 C1／C2；樣本少 |

## Corpus gap

n=14 ≪ ~100。類別先用這批；換 PDF 後再驗證是否還有新類。

## Compile signals (cascade — hints only)

From `3.分析結果/output/123.log`:
- l.57 brace / `\\` inside `{…}` in marks cell
- l.306–312 bare `2x^2` without `$`
- l.501 / l.513 broken `\(...\)` around 角錐體 / `\triangle`
