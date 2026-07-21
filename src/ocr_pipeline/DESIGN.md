# OCR Pipeline redesign — confirmed decisions

## Confirmed
1. Default VLM: `Qwen2.5-VL-7B-Instruct` **4bit** via `VlmClient` (GLM-4.6V-Flash optional adapter)
2. Table: Markdown in Stage2 draft → LaTeX tabular in Stage3
3. Formula delimiters are **context-aware** (not always `$$`):
   - Body display / equation block → `$$...$$`
   - Inline in prose → `$...$`
   - Inside `tabular` cells → `$...$` only (never `$$`)
4. Entrypoint: `run_ocr_pipeline.py` (legacy `extract_questions.py` kept)
5. Post-pass: `sanitize_tex_document` (tabular-aware) after polish / `--no-vlm`

## Workflow
1. **Extract**
   - PDF → PNG (`LayoutAnalyzer`)
   - Surya layout + reading order
   - Dynamic route via `VlmClient`:
     - Formula/Equation → `MathRouter` (MinerU later; VLM fallback today)
     - Text/Title/List → `TextRouter`
     - Table → Markdown (cell math with `$...$`)
2. **Arrange**
   - `DraftAssembler.stitch`
   - `FinalPolisher` → `sanitize_tex_document` → `output/<name>.txt` + `.tex`
3. **Teacher**
   - Edit ≤10 min → manual `latexmk -xelatex` / `xelatex`
   - CLI DX: eng plan DR1–DR9

## Delimiter / HTML sanitizer
| Case | Action |
|------|--------|
| `$$` inside tabular | → `$...$` |
| `<br>` inside table | → `\\` |
| `<br>` outside table | → blank line |
| Unpaired `$` | `% TODO: verify` (fail-open) |
| Wrong column count | Out of scope — human / Approach B |

## Run
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ocr-pipeline.txt
.\.venv\Scripts\python.exe run_ocr_pipeline.py data\sources\123.pdf --limit 1
.\.venv\Scripts\python.exe arrange_only.py output\123.txt --no-vlm
```

## Notes
- Default speed mode: single Stage3 polish (`polish_per_page: false`)
- `polish_per_page`: extract bodies, **one** `\documentclass` wrap
- Surya 2 may require vLLM/llama.cpp; fallback to full-page if needed
- MinerU: deferred (P3) until golden stable; do not reorder ahead of sanitize + Qwen
