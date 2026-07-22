# pdf_converter

Teacher workflow: PDF → OCR draft `.tex` → edit <=10 minutes → compile with XeLaTeX.  
Local folder may still be named `pdf scaner`; the GitHub project is **pdf_converter**.

## Recommended path (new pipeline)

```text
PDF
 → run_ocr_pipeline.py     (Surya layout + VlmClient route + Stage3 polish + sanitize)
 → output/<name>.txt + output/<name>.tex
 → edit .tex ≤10m
 → latexmk -xelatex <name>.tex   (or xelatex)
```

Default VLM: **Qwen2.5-VL-7B-Instruct 4bit** (`config/ocr_pipeline.yaml` → `vlm:`).  
GLM-4.6V-Flash remains optional (`vlm.backend: glm`).

Legacy extract path (`extract_questions.py` → `draft.jsonl`) still works; prefer `run_ocr_pipeline.py` for marking schemes.

## Hardware

RTX 4070 Super **12GB**, 32GB RAM. Prefer Surya via Docker/vLLM so it does not thrash the same GPU as the VLM.

## Setup

```powershell
cd "C:\Users\a1217\OneDrive\桌面\aiworkplace\pdf scaner"
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ocr-pipeline.txt
# Optional layout:
# pip install surya-ocr --no-deps
```

## Teacher loop (golden)

1. Put PDF in `data/sources/` (e.g. `123.pdf`).
2. Run one page:

```powershell
.\.venv\Scripts\python.exe run_ocr_pipeline.py data\sources\123.pdf --limit 1
```

3. CLI ends with (DR1):

```text
TEX: <absolute-path>
Next: edit <=10m, then latexmk -xelatex <file>
WARN: ...          (only if needed; one line)
```

4. Edit the `.tex` (checklist below) <=10 minutes.
5. Compile (manual, or opt-in gate):

```powershell
# manual
cd output
latexmk -xelatex 123.tex

# or opt-in after pipeline / arrange:
.\.venv\Scripts\python.exe arrange_only.py output\123.txt --no-vlm --check-compile
.\.venv\Scripts\python.exe run_ocr_pipeline.py data\sources\123.pdf --limit 1 --reuse-images --check-compile
```

6. Optional: open page PNG under `data/pdf_pages/` beside the PDF and compare.

### Edit checklist

- [ ] Marks / score column looks right  
- [ ] Spot-check ≥3 formulas  
- [ ] At least one table row  
- [ ] No `$$` inside `tabular` cells  
- [ ] Compiles with zero errors after your edits  

### Stage3 silence

At start you see: `Note: Stage3 may take several minutes; silence is OK.`  
Then `Stage3 arrange…` once — **no heartbeat**. Silence for several minutes is normal, not a hang.

### Fast sanitize-only re-run

```powershell
.\.venv\Scripts\python.exe arrange_only.py output\123.txt --no-vlm
```

Same success block as the full pipeline (no Stage3 preflight).

## CLI states (summary)

| Stage | What you see |
|-------|----------------|
| Preflight | `Note: Stage3 may take several minutes; silence is OK.` |
| Layout | `Stage1 layout page N…` / `blocks=k` |
| Fullpage fallback | `WARN: layout fullpage fallback (not golden)` |
| Stage3 | `Stage3 arrange…` then quiet |
| Success | `TEX:` / `Next:` / optional one-line `WARN:` |
| Exit code | `0` if `.tex` written (even with WARN); else non-zero |

Plain text only — no color, no emoji.

## Config notes

| Key | Meaning |
|-----|---------|
| `vlm.backend` | `qwen` (default) or `glm` |
| `vlm.model_name` | Hugging Face id |
| `math.formula_style` | `context` — body `$$`, inline `$`, tabular `$` only |
| `pipeline.polish_per_page` | `false` faster; `true` polishes each page then one wrap |
| `layout.force_backend` | empty = try Surya; `fullpage` forces fallback |

Design detail: `src/ocr_pipeline/DESIGN.md`.  
Plans: `task_plan.md`, `TODOS.md`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Legacy extract path

Still available for the older draft.jsonl flow — see older sections / `UPGRADE_NOTES.md` if needed:

| File | Role |
|------|------|
| `run_extract_pipeline.py` | PDF → images → draft.jsonl |
| `extract_questions.py` | Local VLM extract |
| `jsonl_to_latex.py` | draft → question `.tex` |
| `config/extraction_config.yaml` | Legacy VLM settings |

## Known pitfalls

- Paths with `桌面`: open images via PIL, not broken `file://` URIs  
- PowerShell `-c` eats `$` — put TeX samples in `.py` / test files  
- Do not promote OCR drafts to training sets without review  
- Optional `--check-compile` on `run_ocr_pipeline.py` / `arrange_only.py` (Ship 1.5): prefers `latexmk -xelatex`, else `xelatex`; writes sibling `.log`; keeps `.tex` on failure  

## Deferred (TODOS)

- LayoutArtifact resume  
- OCR overlay PDF (Ship 2)  
- Real MinerU math path (after golden stable)  
