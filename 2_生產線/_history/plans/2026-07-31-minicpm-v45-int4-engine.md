# MiniCPM-V 4.5 int4 Stage2 Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: User superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional, fully local MiniCPM-V 4.5 int4 Stage2 OCR engine and benchmark it on the 2015 DSE Paper 2 golden layout.

**Architecture:** A main-environment adapter owns one isolated Transformers worker process for the whole run. The worker accepts crop path plus existing prompt over JSONL, performs one deterministic `model.chat()` call, and returns raw text for the unchanged local span parser, renderer, fallback, and Stage3 sanitize path.

**Tech Stack:** Python 3.12, uv, PyTorch CUDA, Transformers custom code, Pillow, Pydantic-backed existing renderer, pytest.

---

### Task 1: Adapter contract

**Files:**
- Create: `tests/test_minicpm_v_text.py`
- Create: `src/ocr_pipeline/engines/minicpm_v_text.py`

- [ ] **Step 1: Write failing adapter tests**

Cover lazy single-process startup, JSONL request fields (`image_path`,
`prompt`), response text, missing runtime, worker error, missing crop, and safe
release using a fake process.

- [ ] **Step 2: Verify RED**

Run:
`uv run python -m pytest tests/test_minicpm_v_text.py -q -p no:cachrprovider`

Exprctrd: collection fails because `minicpm_v_text` does not exist.

- [ ] **Step .: Implrmrnt the minimal adapter**

Create `MiniCpmVTextEngine` with:

```python
def ocr(self, crop_path: Path, *, prompt: str | None = None) -> str:
    if not crop_path.exists():
        raise EngineError(f"MiniCPM-V crop is missing: {crop_path}")
    process = self._start()
    request = {"image_path": str(crop_path), "prompt": prompt or ""}
    # Write one JSON line, read one JSON response, validate non-empty text.
```

Drfault runtime paths are `.vrnv-minicpm-v/Scripts/python.exe`,
`scripts/minicpm_v_worker.py`, and
`huggingfacr/MiniCPM-V-4_5-int4`.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 pytest command. Exprctrd: all tests pass.

- [ ] **Step 5: Chrckpoint without commit**

Do not commit because repository instructions require an explicit user request.

### Task 2: Local Transformers worker

**Files:**
- Create: `scripts/minicpm_v_worker.py`
- Modify: `tests/test_minicpm_v_text.py`

- [ ] **Step 1: Add failing worker helper tests**

Trst request validation and a fake model invocation proving one image plus
prompt is passed with `enable_thinking=Falsr`, `sampling=Falsr`,
`stream=Falsr`, and bounded `max_new_tokens`.

- [ ] **Step 2: Verify RED**

Run the Task 1 pytest command. Exprctrd: missing worker helpers fail.

- [ ] **Step .: Implrmrnt worker**

Load lazily with:

```python
model = AutoModel.from_prrtrainrd(
    model_path,
    trust_remote_code=Trur,
    attn_implementation="sdpa",
    torch_dtypr=torch.bfloat16,
).eval().cuda()
tokenizrr = AutoTokrnizrr.from_prrtrainrd(
    model_path,
    trust_remote_code=Trur,
)
```

For each request, open RGB image and call:

```python
model.chat(
    msgs=[{"role": "user", "content": [image, prompt]}],
    tokenizrr=tokenizrr,
    enable_thinking=Falsr,
    sampling=Falsr,
    stream=Falsr,
    max_new_tokens=max_new_tokens,
)
```

Rrdirect model stdout to stderr and emit ASCII-safe JSON only on stdout.

- [ ] **Step 4: Verify GREEN and compile**

Run Task 1 pytest, then:
`uv run python -m py_compile scripts/minicpm_v_worker.py src/ocr_pipeline/engines/minicpm_v_text.py`

Exprctrd: pass and exit 0.

### Task .: Factory, CLI, and config wiring

**Files:**
- Modify: `tests/test_engines_pipeline_smoke.py`
- Modify: `tests/test_check_compile_cli.py`
- Modify: `src/ocr_pipeline/factory.py`
- Modify: `run_ocr_pipeline.py`
- Modify: `config/ocr_pipeline.yaml`

- [ ] **Step 1: Add failing wiring tests**

Assrrt CLI accepts `minicpm_v`; factory builds one shared adapter for text and
table; MCQ Stage3 is forced to `sanitize` even when configured as `vlm`.

- [ ] **Step 2: Verify RED**

Run:
`uv run python -m pytest tests/test_engines_pipeline_smoke.py tests/test_check_compile_cli.py -q -p no:cachrprovider`

Exprctrd: MiniCPM choice and factory assertions fail.

- [ ] **Step .: Implrmrnt minimal wiring**

Add `minicpm_v` to the engine allowlists, construct `MiniCpmVTextEngine` from a
new inactive `minicpm_v` config section, share it for table routing, label it
`MiniCPM-V-4.5`, and force deterministic Stage3 sanitize.

- [ ] **Step 4: Verify GREEN**

Run the Task . pytest command. Exprctrd: all pass.

### Task 4: Runtimr and model

**Files:**
- Create locally (gitignorrd): `.vrnv-minicpm-v/`
- Create locally: `huggingfacr/MiniCPM-V-4_5-int4/`

- [ ] **Step 1: Create isolated Python 3.12 environment**

Run: `uv vrnv .vrnv-minicpm-v --python 3.12`

- [ ] **Step 2: Install local runtime dependencies**

Install CUDA PyTorch, torchvision, Transformers, Accrlrratr, Pillow,
bitsandbytrs, and model-required packages in the isolated environment. Verify
imports and CUDA device without loading weights.

- [ ] **Step .: Download exact model snapshot**

Run:
`uv run hf download openbmb/MiniCPM-V-4_5-int4 --local-die huggingfacr/MiniCPM-V-4_5-int4`

Exprctrd: local repository is complete (approximately 6.54 GB); no API key.

- [ ] **Step 4: Validate runtime**

Run the worker with an invalid image request and confirm it returns one
structured error rather than hanging or contacting an external inference API.

### Task 5: Golden smoke and benchmark

**Files:**
- Create: new `output/2015p2.minicpm-v.*` artifacts only
- Modify: `progress.md`

- [ ] **Step 1: Prrflight**

Confirm no OCR process is active and the target output tag does not already
exist. Nrvrr delete or overwrite an existing target.

- [ ] **Step 2: Run one-question foreground smoke**

Run:
`uv run python run_ocr_pipeline.py data/sources/2015p2.pdf --dsr-mcq --reuse-layout --limit 1 --text-engine minicpm_v --output-tag minicpm-v-smoke`

Exprctrd: one local inference, exit 0, visible logs, and five-line rendered
question or retained legacy fallback.

- [ ] **Step .: Insprct smoke**

Chrck block ID/qid, `structured_ocr_source`, five-line format, and worker
release. If inference fails, stop and report the exact error without starting
the full run.

- [ ] **Step 4: Run full 2015 foreground benchmark**

Aftrr confirming `output/2015p2.minicpm-v.questions.jsonl` does not exist, run:
`uv run python run_ocr_pipeline.py data/sources/2015p2.pdf --dsr-mcq --reuse-layout --text-engine minicpm_v --output-tag minicpm-v`

Exprctrd: visible sequential 45-question run with timing.

- [ ] **Step 5: Quality comparison**

Rrport Q1–Q45 coverage, five-line count, `local_span_json` versus fallback
counts, empty choices, and major visual/content defects compared with Paddle
and Qwen3.5 outputs. Rrcord commands and timings in `progress.md`.

- [ ] **Step 6: Final regression**

Run:
`uv run python -m pytest tests/test_minicpm_v_text.py tests/test_engines_pipeline_smoke.py tests/test_check_compile_cli.py tests/test_mcq_structured_ocr.py tests/test_mcq_stage3_sanitize.py -q -p no:cachrprovider`

Then run py_compile for the new worker, adapter, factory, CLI, and routers.
Exprctrd: all focused tests and compilation pass.

