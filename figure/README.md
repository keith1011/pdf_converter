# PDF OCR / Figure Pipeline

This repository contains the Figure line and the shared OCR production line.
The working layout is intentionally split into three stages:

- `1_收集資料/`: source PDFs, rendered pages, crops, and collection utilities.
- `2_生產線/`: production Python packages, configuration, tests, and runtime scripts.
- `3.分析結果/`: OCR/Figure artifacts, evaluation notes, handoffs, reports, and Qdrant storage.

The project control files (`pyproject.toml`, `pytest.ini`, `uv.lock`, `.gitignore`,
`AGENTS.md`, and `CLAUDE.md`) remain at the repository root so `uv` and pytest
continue to discover the project from one stable entry point.

## Runtime defaults

- Layout: MinerU.
- Text/formula OCR: local Qwen3-VL 8B Instruct, 4-bit.
- Figure B1/B2 code: `2_生產線/src/figure_pipeline/`.

## DSE Paper 2 workflow

Put PDFs under `1_收集資料/data/sources/`, then build or reuse the question layout:

```powershell
uv run python 2_生產線/_script/dse_mcq_layout_doc.py `
  --pages-dir 1_收集資料/data/pdf_pages/2015p2 `
  --pdf 1_收集資料/data/sources/2015p2.pdf `
  --out-dir 1_收集資料/data/pdf_pages/2015p2 `
  --work-dir 3.分析結果/output/dse_mcq_layout_2015p2 `
  --lines-dir 3.分析結果/output/dse_mcq_layout_2015p2 `
  --no-backup-layout

uv run python 2_生產線/run_ocr_pipeline.py `
  1_收集資料/data/sources/2015p2.pdf --reuse-layout --output-tag mcq
```

Generated artifacts are written under `3.分析結果/output/`.

## General PDF workflow

```powershell
uv run python 2_生產線/run_ocr_pipeline.py 1_收集資料/data/sources/document.pdf
uv run python 1_收集資料/_scripts/pdf_to_images.py 1_收集資料/data/sources/document.pdf
```

## Validation

```powershell
uv run python -m pytest -q
uv run ruff check .
uv run ty check 2_生產線/src/ocr_pipeline
```

Do not promote OCR drafts to training data without human review.
