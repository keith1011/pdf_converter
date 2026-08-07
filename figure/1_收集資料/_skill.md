# Collect data

Use this guide for research, downloads, source PDFs, provenance, page rendering,
and crop preparation before OCR.

## Skill routing

Use only what the task needs:

- `browse`: targeted web research and source inspection.
- `scrape`: repeatable extraction from pages or datasets.
- `pdf:pdf`: inspect or transform PDF source material.
- `context7-mcp`: current library, SDK, API, or CLI documentation.

Read the selected skill before acting.

## Workflow

1. Research and review candidate sources.
2. Archive only sources selected for actual use under `1_收集資料/`, normally
   below `data/sources/`.
3. Add a sibling `<name>.source.md` containing the original URL, retrieval date,
   intended use, license or attribution, and any transformations.
4. Use `_scripts/` to normalize sources or render pages/crops into
   `data/pdf_pages/`.
5. Hand prepared inputs to `2_生產線/`; keep runtime OCR code out of this stage.

Do not save rejected search results. Preserve original source files whenever
possible.
