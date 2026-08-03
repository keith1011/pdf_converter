# Production stage

Purpose: run the Figure and OCR production pipeline.

Contents:

- `2_生產線/src/`: `figure_pipeline` and `ocr_pipeline` Python packages.
- `2_生產線/config/`: MinerU/Qwen/PaddleOCR and subject-profile configuration.
- `2_生產線/_script/`: operational and phase CLIs moved from the former `scripts/`.
- `2_生產線/tests/`: regression and Figure pipeline tests.
- `2_生產線/homelab/`: publish/ingest and deployment helpers.
- `2_生產線/run_ocr_pipeline.py`: main runtime entrypoint.
- `2_生產線/arrange_only.py`: Stage3-only re-finalization entrypoint.

Commands are launched from the repository root so paths resolve to the three
classified stages. Project metadata stays at the root for `uv`, pytest, and ruff.
