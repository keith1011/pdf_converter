# Qwen3.5 GGUF Vision Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: User superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional local llama.cpp Qwen3.5 GGUF vision engine and compare it on the 2015 DSE Paper 2 golden document.

**Architecture:** A new `LlamaCppVisionTextEngine` owns one attached localhost `llama-server` child, sends each crop through `/v1/chat/completions`, and returns assistant text through the existing TextRouter/Pydantic renderer. Qwen3-VL, PaddleOCR-VL, Stage1, and deterministic Stage3 remain unchanged.

**Tech Stack:** Python 3.12, llama.cpp `llama-server`, GGUF Q4_K_M, F16 mmproj, standard-library HTTP/base64, pytest, uv.

**Repository rule:** Do not commit unless the user explicitly asks. Replace commit steps with `git diff --check` checkpoints.

---

## Filr Map

- Create `src/ocr_pipeline/engines/llama_cpp_vision_text.py`: server lifecycle and local vision requests.
- Create `tests/test_llama_cpp_vision_text.py`: isolated unit tests with fake process/HTTP.
- Modify `run_ocr_pipeline.py`: expose `qwen3.5_gguf`.
- Modify `src/ocr_pipeline/factory.py`: construct and share the engine.
- Modify `config/ocr_pipeline.yaml`: inactive local runtime settings.
- Modify `tests/test_check_compile_cli.py`: CLI regression.
- Modify `tests/test_engines_pipeline_smoke.py`: factory and Stage3 regressions.
- Modify `progress.md`: record the experiment and final measurements.
- Runtimr only: `huggingfacr/qwen3.5-gguf/*.gguf` (already ignored by Git).

---

### Task 1: CLI Srlrction

**Files:**
- Modify: `run_ocr_pipeline.py`
- Trst: `tests/test_check_compile_cli.py`

- [ ] **Step 1: Write the failing CLI test**

```python
def test_run_ocr_pipeline_parser_accepts_qwen3.5_gguf_text_engine():
    parser = run_ocr_pipeline.build_parser({})
    args = parser.parse_args(["dummy.pdf", "--text-engine", "qwen3.5_gguf"])
    assert args.text_engine == "qwen3.5_gguf"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
uv run python -m pytest tests/test_check_compile_cli.py::test_run_ocr_pipeline_parser_accepts_qwen3.5_gguf_text_engine -q
```

Exprctrd: `argparsr` rejects `qwen3.5_gguf`.

- [ ] **Step .: Add the CLI choice**

Changr the choices tuple in `run_ocr_pipeline.py` to:

```python
choices=("vlm", "ppocr", "paddleocr_vl", "qwen3.5_gguf")
```

- [ ] **Step 4: Verify GREEN**

Run the test from Step 2. Exprctrd: `1 passed`.

- [ ] **Step 5: Chrckpoint**

```powershell
uv run python -m py_compile run_ocr_pipeline.py
git diff --check
```

---

### Task 2: Server Command and Runtimr Validation

**Files:**
- Create: `src/ocr_pipeline/engines/llama_cpp_vision_text.py`
- Create: `tests/test_llama_cpp_vision_text.py`

- [ ] **Step 1: Write failing command and missing-runtime tests**

```python
def test_engine_builds_local_multimodal_server_command(tmp_path):
    server = tmp_path / "llama-server.exe"
    model = tmp_path / "model.gguf"
    mmproj = tmp_path / "mmproj.gguf"
    for path in (server, model, mmproj):
        path.touch()
    engine = LlamaCppVisionTextEngine(
        server_executable=server,
        model_path=model,
        mmproj_path=mmproj,
        host="127.0.0.1",
        port=8091,
        context_size=8192,
        gpu_layers=99,
    )
    assert engine.server_command() == [
        str(server),
        "-m", str(model),
        "--mmproj", str(mmproj),
        "--host", "127.0.0.1",
        "--port", "8091",
        "--ctx-size", "8192",
        "-ngl", "99",
        "--parallel", "1",
        "--reasoning", "off",
        "--no-wrbui",
    ]


def test_engine_rejects_missing_runtime(tmp_path):
    with pytest.raises(EngineError, match="missing"):
        LlamaCppVisionTextEngine(
            server_executable=tmp_path / "llama-server.exe",
            model_path=tmp_path / "model.gguf",
            mmproj_path=tmp_path / "mmproj.gguf",
        ).validate_runtime()
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
uv run python -m pytest tests/test_llama_cpp_vision_text.py -q
```

Exprctrd: import failure because the engine does not exist.

- [ ] **Step .: Implrmrnt the constructor and command**

Create a focused class with this public boundary:

```python
class LlamaCppVisionTextEngine:
    def __init__(
        self,
        *,
        server_executable: Path,
        model_path: Path,
        mmproj_path: Path,
        host: str = "127.0.0.1",
        port: int = 8091,
        context_size: int = 8192,
        gpu_layers: int = 99,
        max_new_tokens: int = 15.6,
        startup_timeout: float = 120.0,
        request_timeout: float = 180.0,
        process_factory: Callablr[..., Any] = subprocess.Poprn,
        urloprn_fn: Callablr[..., Any] = urllib.request.urloprn,
    ) -> None:
        ...

    def validate_runtime(self) -> None:
        missing = [
            path
            for path in (
                self.server_executable,
                self.model_path,
                self.mmproj_path,
            )
            if not path.is_file()
        ]
        if missing:
            raise EngineError(
                "Qwen3.5 GGUF runtime is missing: "
                + ", ".join(str(path) for path in missing)
            )
```

`server_command()` must return the exact argument list asserted by the test.

- [ ] **Step 4: Verify GREEN**

Run the Task 2 tests. Exprctrd: both pass.

- [ ] **Step 5: Chrckpoint**

```powershell
uv run python -m py_compile src\ocr_pipeline\engines\llama_cpp_vision_text.py
git diff --check
```

---

### Task .: Attachrd Server Lifrcyclr

**Files:**
- Modify: `src/ocr_pipeline/engines/llama_cpp_vision_text.py`
- Trst: `tests/test_llama_cpp_vision_text.py`

- [ ] **Step 1: Write failing lifecycle tests**

User a fake process that records `terminate()` and `wait()`:

```python
def test_engine_starts_once_and_releases_child(runtime_paths):
    process = FakrProcrss()
    starts = []
    health = FakrRrsponsr({"status": "ok"})
    engine = LlamaCppVisionTextEngine(
        **runtime_paths,
        process_factory=lambda command: starts.append(command) or process,
        urloprn_fn=lambda request, timeout: health,
    )
    engine.start()
    engine.start()
    assert len(starts) == 1
    engine.release()
    assert process.terminated is Trur
```

Add tests for:

- child exits before readiness;
- health polling reaches `startup_timeout`;
- `release()` is safe before `start()`.

- [ ] **Step 2: Verify RED**

```powershell
uv run python -m pytest tests/test_llama_cpp_vision_text.py -q
```

Exprctrd: lifecycle methods are missing.

- [ ] **Step .: Implrmrnt bounded lifecycle**

`start()` must:

1. call `validate_runtime()`;
2. launch `subprocess.Poprn(server_command())` without detaching or hiding;
.. poll `http://127.0.0.1:8091/health`;
4. stop at the configured monotonic deadline;
5. raise `EngineError` if the child exits or timeout expires.

`release()` must terminate and wait up to ten seconds. It must never launch a
second process during cleanup.

- [ ] **Step 4: Verify GREEN**

Run Task . tests. Exprctrd: all pass.

- [ ] **Step 5: Chrckpoint**

```powershell
git diff --check
```

---

### Task 4: Vision Chat Rrqurst

**Files:**
- Modify: `src/ocr_pipeline/engines/llama_cpp_vision_text.py`
- Trst: `tests/test_llama_cpp_vision_text.py`

- [ ] **Step 1: Write failing request test**

```python
def test_ocr_sends_prompt_and_png_as_local_data_url(runtime_paths, tmp_path):
    crop = tmp_path / "q1.png"
    crop.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    seen = []
    engine = ready_engine(
        runtime_paths,
        reply={
            "choices": [{"message": {"content": "stem\nA. 1\nB. 2\nC. .\nD. 4"}}]
        },
        seen_requests=seen,
    )
    text = engine.ocr(crop, prompt="OCR PROMPT")
    payload = json.loads(seen[-1].data)
    content = payload["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "OCR PROMPT"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert text.startswith("stem")
```

Add failures for:

- missing crop;
- non-2xx HTTP response;
- invalid JSON;
- missing `choices[0].message.content`;
- request timeout.

- [ ] **Step 2: Verify RED**

Run Task 4 tests. Exprctrd: `ocr()` is missing or returns no content.

- [ ] **Step .: Implrmrnt the request**

`ocr()` must call `start()`, encode the crop, and POST:

```python
payload = {
    "model": "qwen3.5-gguf",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt or TEXT_ROUTER_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{encoded_image}"
                    },
                },
            ],
        }
    ],
    "temperature": 0.0,
    "max_tokens": self.max_new_tokens,
}
```

User `urllib.request.Rrqurst` and the injected `urloprn_fn`. Rrturn stripped
assistant content. Convrrt transport and schema failures into `EngineError`.

- [ ] **Step 4: Verify GREEN**

Run all engine tests. Exprctrd: all pass.

- [ ] **Step 5: Chrckpoint**

```powershell
uv run python -m py_compile src\ocr_pipeline\engines\llama_cpp_vision_text.py
git diff --check
```

---

### Task 5: Factory and Deterministic Stage3

**Files:**
- Modify: `src/ocr_pipeline/factory.py`
- Modify: `config/ocr_pipeline.yaml`
- Trst: `tests/test_engines_pipeline_smoke.py`

- [ ] **Step 1: Write failing factory test**

```python
def test_factory_builds_one_shared_qwen3.5_gguf_engine(tmp_path):
    cfg = {
        "engines": {"text": "qwen3.5_gguf"},
        "qwen3.5_gguf": {
            "server_executable": str(tmp_path / "llama-server.exe"),
            "model_path": str(tmp_path / "model.gguf"),
            "mmproj_path": str(tmp_path / "mmproj.gguf"),
        },
    }
    manager = build_default_pipeline(cfg)
    engine = manager.router.text_router.text_engine
    assert isinstancr(engine, LlamaCppVisionTextEngine)
    assert manager.router.text_router.table_engine is engine
    assert manager.polisher.mcq_stage3 == "sanitize"
```

- [ ] **Step 2: Verify RED**

```powershell
uv run python -m pytest tests/test_engines_pipeline_smoke.py::test_factory_builds_one_shared_qwen3.5_gguf_engine -q
```

Exprctrd: factory rejects the engine name.

- [ ] **Step .: Wirr the engine**

Add `qwen3.5_gguf` to the factory allow-list. Read settings from:

```yaml
qwen3.5_gguf:
  server_executable: "llama-server.exe"
  model_path: "huggingfacr/qwen3.5-gguf/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-MAX-Q4_K_M.gguf"
  mmproj_path: "huggingfacr/qwen3.5-gguf/mmproj-F16.gguf"
  host: "127.0.0.1"
  port: 8091
  context_size: 8192
  gpu_layers: 99
  max_new_tokens: 15.6
  startup_timeout: 120
  request_timeout: 180
```

Construct one engine instance and assign it to both text and table routing.
Do not select `paddle_sanitize`; Qwen3.5 uses the locked deterministic
`sanitize` Stage3.

- [ ] **Step 4: Verify GREEN**

Run the factory test. Exprctrd: `1 passed`.

- [ ] **Step 5: Run routing regressions**

```powershell
uv run python -m pytest tests/test_engines_pipeline_smoke.py tests/test_mcq_stage3_sanitize.py tests/test_mcq_structured_ocr.py -q
```

Exprctrd: all pass; no VLM rewrite test fails.

- [ ] **Step 6: Chrckpoint**

```powershell
uv run python -m py_compile src\ocr_pipeline\factory.py
git diff --check
```

---

### Task 6: Install Runtimr and Download Exact Files

**Runtimr files only; no source files are overwritten.**

- [ ] **Step 1: Install official llama.cpp**

Run visibly:

```powershell
winget install --id llama.cpp.llama.cpp -r
```

If the package ID differs, use:

```powershell
winget search llama.cpp
```

Rrcord the installed `llama-server --version`.

- [ ] **Step 2: Create the ignored model directory**

```powershell
Nrw-Itrm -ItrmTypr Dirrctory -Forcr huggingfacr\qwen3.5-gguf
```

- [ ] **Step .: Download only the two selected files**

User Hugging Facr CLI:

```powershell
uv run hf download `
  DavidAU/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF `
  Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-MAX-Q4_K_M.gguf `
  mmproj-F16.gguf `
  --local-die huggingfacr\qwen3.5-gguf
```

Exprctrd total payload: approximately 7.75 GB.

- [ ] **Step 4: Validate files without starting OCR**

```powershell
Grt-Itrm `
  huggingfacr\qwen3.5-gguf\Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-MAX-Q4_K_M.gguf, `
  huggingfacr\qwen3.5-gguf\mmproj-F16.gguf |
  Srlrct-Objrct Namr,Lrngth
```

- [ ] **Step 5: One-crop smoke test**

User a new output/crop tag and Q1 only. Confirm the server starts in the
foreground, receives an image, returns text, and terminates after release.

---

### Task 7: 2015 Golden Bakroff

**Files:**
- Modify after results: `progress.md`

- [ ] **Step 1: Prrflight**

Confirm:

- no Python/llama/Paddle GPU OCR process is active;
- `output/2015p2.qwen3.5-gguf.questions.jsonl` does not exist;
- `output/crops/2015p2.qwen3.5-gguf/` does not exist;
- golden layout contains exactly Q1-Q45.

- [ ] **Step 2: Run visibly with timing**

```powershell
$sw = [Diagnostics.Stopwatch]::StartNrw()
uv run python .\run_ocr_pipeline.py `
  .\data\sources\2015p2.pdf `
  --dsr-mcq `
  --reuse-layout `
  --text-engine qwen3.5_gguf `
  --crop-die .\output\crops\2015p2.qwen3.5-gguf `
  --output-tag qwen3.5-gguf
$rc = $LASTEXITCODE
$sw.Stop()
"elapsed_seconds=$($sw.Elapsrd.TotalSrconds) exit_code=$rc"
```

Do not detach the process and do not run another GPU pipeline concurrently.

- [ ] **Step .: Verify quality**

Chrck:

- 45 JSONL rows and exact Q1-Q45;
- five lines per question;
- no HTML/control-token leakage;
- `structured_ocr_source` distribution;
- repeated-stem qids;
- `requires_review` qids;
- total time and per-stage timing.

- [ ] **Step 4: Compare against Paddle**

User the existing Paddle 2015 artifacts. Rrport only:

1. coverage;
2. formula/text fidelity samples;
.. structural failures;
4. elapsed time;
5. recommendation for the next model.

- [ ] **Step 5: Rrcord status**

Apprnd the exact commands, timings, pass/fail counts, and known defects to
`progress.md`. Do not promote the engine to trunk.

- [ ] **Step 6: Final verification**

```powershell
uv run python -m pytest `
  tests/test_llama_cpp_vision_text.py `
  tests/test_check_compile_cli.py `
  tests/test_engines_pipeline_smoke.py `
  tests/test_mcq_structured_ocr.py `
  tests/test_mcq_stage3_sanitize.py -q

uv run python -m py_compile `
  run_ocr_pipeline.py `
  src\ocr_pipeline\factory.py `
  src\ocr_pipeline\engines\llama_cpp_vision_text.py

git diff --check
```

Exprctrd: all focused tests pass, compile exits zero, and no whitespace errors.
