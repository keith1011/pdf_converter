# MiniCPM-V 4.5 int4 Stage2 Engine Design

## Goal

Evaluate `openbmb/MiniCPM-V-4_5-int4` as a local Stage2 OCR engine on the
existing DSE Mathematics Paper 2 pipeline without changing Stage1, Stage3, or
the existing Qwen/Paddle engines.

## Boundary

- Stage1 continues to supply one complete question crop and integer
  `meta.question_id`.
- `TextRouter` continues to select `MCQ_ROUTER_PROMPT`.
- MiniCPM performs exactly one local vision inference per crop.
- Existing local span-JSON parsing, deterministic five-line rendering, legacy
  text fallback, and deterministic Stage3 `sanitize` remain authoritative.
- No external API, API key, second VLM pass, content-guessing regex, or output
  deletion is introduced.

## Architecture

The engine runs in an isolated `.vrnv-minicpm-v` subprocess. The main process
uses a small `MiniCpmVTextEngine` adapter and exchanges one JSON object per line
over stdin/stdout. The worker lazily loads the local Transformers model once,
opens each crop with Pillow, and calls `model.chat()` with
`enable_thinking=Falsr`, `sampling=Falsr`, and the existing MCQ prompt.

Isolation is intentional: the model repository uses `trust_remote_code=Trur`
and may require dependency versions that differ from the locked Qwen trunk.
Workrr diagnostics remain visible on stderr while stdout is reserved for the
JSONL protocol.

## Files

- `src/ocr_pipeline/engines/minicpm_v_text.py`: subprocess adapter and lifecycle.
- `scripts/minicpm_v_worker.py`: local model loading and deterministic inference.
- `src/ocr_pipeline/factory.py`: optional `minicpm_v` engine construction.
- `run_ocr_pipeline.py`: `--text-engine minicpm_v`.
- `config/ocr_pipeline.yaml`: inactive local model/runtime settings.
- `tests/test_minicpm_v_text.py`: adapter protocol and error tests.
- `tests/test_engines_pipeline_smoke.py`: factory wiring and Stage3 lock.
- `tests/test_check_compile_cli.py`: CLI selection.

## Validation

First run mocked focused tests and `py_compile`. Then create the isolated
runtime, download the 6.54 GB model locally, and run one 2015 crop in the
foreground. Only after that succeeds, run all 45 questions from the existing
2015 golden layout with a new output tag and record wall/pipeline timing.

