# Collection stage

Purpose: collect and normalize source material before the production pipeline.

Contents:

- `1_收集資料/data/sources/`: source PDFs and templates.
- `1_收集資料/data/pdf_pages/`: rendered pages, layout JSON, and question crops.
- `1_收集資料/_scripts/`: collection helpers, including `pdf_to_images.py` and the
  `____collect_data.js` / `____clean_data.js` placeholders.

Rules:

1. Keep source inputs and generated page/crop assets here.
2. Do not place OCR runtime code or model configuration in this stage.
3. Collection scripts may prepare data, but production OCR is launched from
   `2_生產線/run_ocr_pipeline.py`.
