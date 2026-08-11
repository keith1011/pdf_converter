# pdf_converter

P-ocr feedstock pipeline: PDF → OCR drafts → editable `.txt`, `.tex`, and
`.pageir.json`.

The locked DSE MATH CP Paper 2 path uses:

- specialized DSE MCQ layout regions from RapidOCR lines;
- MinerU for the general layout trunk;
- local `Qwen/Qwen3-VL-8B-Instruct` in 4-bit mode for Stage2;
- deterministic Stage3 sanitize for MCQ;
- one PageIR segment and one `questions.jsonl` row per question.

The current project handoff is `handoff_ocr.md`.

## Setup

```powershell
uv sync
```

Python 3.12 is required. The main environment is `.venv`.

## DSE Paper 2 workflow

Put the PDF in `data/sources/`, then build or reuse the question layout:

```powershell
uv run python scripts/dse_mcq_layout_doc.py `
  --pages-dir data/pdf_pages/2015p2 `
  --pdf data/sources/2015p2.pdf `
  --out-dir data/pdf_pages/2015p2 `
  --work-dir output/dse_mcq_layout_2015p2 `
  --lines-dir output/dse_mcq_layout_2015p2 `
  --no-backup-layout

uv run python run_ocr_pipeline.py `
  data/sources/2015p2.pdf --reuse-layout --output-tag mcq
```

Generated artifacts are written under `output/`:

- `<doc>.txt`
- `<doc>.tex`
- `<doc>.pageir.json`
- `<doc>.questions.jsonl`
- `<doc>.quality.json`
- `<doc>.timing.txt`

Only one OCR pipeline may use the 12 GB GPU at a time.

## General PDF workflow

```powershell
uv run python run_ocr_pipeline.py data/sources/document.pdf
```

Useful options:

- `--limit N`
- `--reuse-images`
- `--reuse-layout`
- `--skip-polish`
- `--output-tag TAG`
- `--check-compile`

`1_收集資料/_scripts/pdf_to_images.py` remains a lightweight page-rendering utility used by the
cross-year layout runner.

## Tests

```powershell
uv run python -m pytest -q
uv run ruff check .
uv run ty check src/ocr_pipeline
```

Do not promote OCR drafts to training data without human review.
