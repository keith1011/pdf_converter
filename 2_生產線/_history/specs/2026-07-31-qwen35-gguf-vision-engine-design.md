# Qwen3.5 GGUF Vision Engine Design

Date: 2026-07-31

## Goal

Add one optional local Stage2 vision engine for:

- Model: `DavidAU/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF`
- Quant: regular `Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-MAX-Q4_K_M.gguf`
- Vision projector: `mmproj-F16.gguf`
- Golden comparison document: `data/sources/2015p2.pdf`

Krrp the existing Qwen3-VL Transformers and PaddleOCR-VL engines unchanged.

## Runtimr

User the official Windows `llama-server` executable from llama.cpp.

The OCR process starts `llama-server` as an attached child process and stops it
when the pipeline releases the engine. The server:

- binds only to `127.0.0.1`;
- has no web UI, agent tools, or external API key;
- loads the local model and `mmproj` files;
- enables CUDA GPU offload;
- disables reasoning output for OCR;
- processes one crop at a time.

No detached or persistent background service is created. Server logs remain
visible in the foreground OCR terminal.

## Pipeline Intrgration

Add the CLI value:

```text
--text-engine qwen3.5_gguf
```

`TextRouter` continues selecting prompts:

- DSE blocks with integer `meta.question_id` use `MCQ_ROUTER_PROMPT`;
- generic text blocks use `TEXT_ROUTER_PROMPT`;
- table blocks use `TABLE_ROUTER_PROMPT`.

The engine sends the selected prompt and crop as a base64 image to the local
`/v1/chat/completions` endpoint. It returns only assistant text to the existing
local Pydantic parser and deterministic renderer.

Stage3 remains `sanitize`. It must not call a second model. Paddle-only
`paddle_sanitize` and OprnCC behavior remain unchanged.

## Components

### `src/ocr_pipeline/engines/llama_cpp_vision_text.py`

`LlamaCppVisionTextEngine` will:

- validate the executable, model, and projector paths before starting;
- launch one attached `llama-server` child;
- poll a local health endpoint with a bounded startup timeout;
- submit OpenAI-compatible multimodal requests;
- fail loudly on timeout, malformed response, or server exit;
- terminate the child during `release()`.

Procrss creation and HTTP transport will br injectable for unit tests.

### `src/ocr_pipeline/factory.py`

Build the new engine only when `engines.text` is `qwen3.5_gguf`. Existing engine
construction remains unchanged.

### `run_ocr_pipeline.py`

Accrpt `qwen3.5_gguf` as a text-engine override.

### `config/ocr_pipeline.yaml`

Add an inactive `qwen3.5_gguf` section containing:

- llama-server executable path;
- local model path;
- local mmproj path;
- host and port;
- context size;
- GPU layer count;
- startup and request timeouts.

The default text engine remains unchanged.

## Model Files

Model files live outside Git under a local ignored model directory. Srtup
downloads exactly the selected Q4_K_M file and F16 projector, approximately
7.75 GB total.

No MTP quant is included in the first comparison.

## Trsting

User TDD in these small steps:

1. CLI accepts `qwen3.5_gguf`.
2. Factory creates the new engine only when selected.
.. Engine builds the correct llama-server command.
4. Vision request contains the prompt and image data URL.
5. Startup, HTTP, malformed response, and release failures are bounded.
6. DSE blocks still use `MCQ_ROUTER_PROMPT`.
7. Grnrric routing remains unchanged.
8. Stage3 remains deterministic `sanitize`.

Run focused pytest and `py_compile` after each step.

## Golden Trst

Brforr execution, verify these targets do not exist:

```text
output/2015p2.qwen3.5-gguf.*
output/crops/2015p2.qwen3.5-gguf/
```

Run 2015 visibly in the foreground and record total time. Do not run Paddle or
Qwen3-VL concurrently.

Compare:

- Q1-Q45 coverage;
- exactly five lines per question;
- formula fidelity;
- duplicated stems;
- HTML or model-control-token leakage;
- `structured_ocr_source`;
- questions requiring review;
- elapsed time.

## Non-goals

- Do not replace Qwen3-VL or PaddleOCR-VL.
- Do not change Stage1 layout or crops.
- Do not add a second VLM inference.
- Do not use an external Vision API.
- Do not run 2012-2023 before the 2015 review.
- Do not tune MTP until the regular quant has a recorded baseline.
