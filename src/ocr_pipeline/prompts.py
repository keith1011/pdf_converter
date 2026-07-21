"""Shared prompt rules: all formulas/equations must be proper LaTeX."""

from __future__ import annotations

# Canonical math rules injected into Stage2 + Stage3 prompts.
LATEX_MATH_RULES = """
【數學公式硬性規則 — 全部必須遵守】
凡是公式 / 方程式 / 代數表達式，一律輸出「標準 LaTeX」，禁止純文字寫法：

1. 分數：禁止 a/b 或 a÷b → 必須 \\frac{a}{b}
2. 指數：禁止 Unicode 上標（如 x²、n⁹）→ 必須 x^{2}、n^{9}
3. 下標：禁止 Unicode 下標 → 必須 a_{1}、x_{i}
4. 根號：禁止 √ → 必須 \\sqrt{...} 或 \\sqrt[n]{...}
5. 乘號：變數相乘可寫 xy 或 x\\cdot y；禁止用 × 字元，改 \\times
6. 獨立成行的公式／方程式（正文，不在表格內）：用 $$...$$
7. 行內公式（夾在文句中）：用 $...$
8. 表格／tabular 儲存格內：只用 $...$，禁止 $$...$$
9. 希臘字母：α→\\alpha，β→\\beta，π→\\pi，θ→\\theta，Δ→\\Delta 等
10. 不等號：≤→\\le，≥→\\ge，≠→\\ne，≈→\\approx
11. 絕對值：|x| → \\lvert x\\rvert 或 |x|（在數學模式內）
12. 禁止輸出「看起來像數學的純文字」；每個公式都要能直接放進 LaTeX 編譯。
""".strip()


MATH_ROUTER_PROMPT = f"""你正在看一張「獨立數學公式／方程式」圖片。

任務：只輸出該公式的標準 LaTeX 本體（不要 $$ 包裹、不要說明、不要 markdown）。

{LATEX_MATH_RULES}

只輸出公式本身，例如：
\\frac{{n^{{9}}}}{{(m^{{3}}n^{{-7}})^{{5}}}}
"""


TEXT_ROUTER_PROMPT = f"""請提取圖片中的全部文字，保持繁體中文與英文原貌。

{LATEX_MATH_RULES}

額外：
- 行內公式用 $...$ 包裹。
- 獨立成行的公式／方程式用 $$...$$。
- 不加任何解釋、標題或 markdown 圍欄。
"""


TABLE_ROUTER_PROMPT = f"""請將圖片中的表格轉成 Markdown 表格。
保持繁體中文與英文原貌。

{LATEX_MATH_RULES}

表格儲存格內若有公式，必須用 $...$ 包成標準 LaTeX（例如 $\\frac{{a}}{{b}}$），禁止 $$...$$，禁止 a/b 純文字分數。
不加任何解釋。
"""


POLISH_PROMPT_HEADER = f"""你是一個 LaTeX 排版專家。請將以下草稿內容修正並排版。

{LATEX_MATH_RULES}

其他要求：
1. 繁體中文流暢；修正明顯 OCR 錯字；不要發明草稿沒有的內容。
2. Markdown 表格轉成 LaTeX tabular（可用 booktabs）。
3. 文件用 \\documentclass[12pt]{{ctexart}}，並 \\usepackage{{amsmath,amssymb,booktabs}}。
4. 不要輸出 <|end_of_box|> 或其他特殊 token。
5. 正文塊級公式用 $$...$$；行內用 $...$；tabular 儲存格內只用 $...$，禁止 $$。
6. 殘留 HTML（如 <br>）轉成 LaTeX（表內用 \\\\，表外用空行）。
7. <<<TEX>>> 內只輸出完整 LaTeX 源碼，禁止 markdown 圍欄（```）與前後說明文字。

請嚴格用下列標記輸出兩段（不要其他說明）：

<<<TXT>>>
（純文本；其中公式仍須是標準 LaTeX，可用 $...$ / $$...$$；表內只用 $）
<<<TEX>>>
（完整可編譯 LaTeX：preamble + \\begin{{document}}...\\end{{document}}）

草稿：
"""
