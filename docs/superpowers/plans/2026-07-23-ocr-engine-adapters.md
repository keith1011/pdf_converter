# P-ocr OCR Engine Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make P-ocr’s feedstock OCR pipeline pluggable (`LayoutEngine` / `TextEngine` / `FormulaEngine`) so we can compare `qwen-vl`, `got-ppocr`, and `mineru-ppocr` on the same `.tex`/`.txt`/`.pageir.json` contract.

**Architecture:** Keep `PipelineManager` + content-first finalize shared. Swap only engine adapters via config. Experiment stacks skip Stage3 VLM polish. Log wall-clock per stage; score teacher edit time + formula quality only.

**Tech Stack:** Python 3.11+ (repo uses 3.14 locally), existing `ocr_pipeline` package, pytest, YAML config. New optional deps per branch: `doclayout-yolo`, Hugging Face `transformers` GOT (`stepfun-ai/GOT-OCR2_0` / GOT-OCR-2.0-hf), `paddleocr` (Traditional Chinese), `mineru` + UniMERNet path.

**Spec:** `docs/superpowers/specs/2026-07-23-ocr-engine-adapters-design.md`

## Global Constraints

- Product name is **P-ocr**; OCR is feedstock only (no Chat UI in this plan).
- Shared contract: `.tex` + `.txt` + `.pageir.json`; no `if backend == ...` inside `segmenter` / `content_first`.
- Experiment branches (`got-ppocr`, `mineru-ppocr`): **no Stage3 VLM polish**.
- Missing engine deps: **fail loud** at startup (no silent Qwen fallback on those branches).
- 12GB VRAM: keep `PipelineLock`; never dual-run `run_ocr_pipeline`.
- Scored metrics: edit time + formulas + compile; **speed logged only** (not ranking weight).
- GLM: delete local weights/cache first; keep `glm_client.py` until later cleanup task.
- Always run tests with: `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest …`

## File map

| Path | Responsibility |
|------|----------------|
| `src/ocr_pipeline/engines/base.py` | Protocols + `EngineError` |
| `src/ocr_pipeline/engines/timing.py` | Stage timer helper (logged, not scored) |
| `src/ocr_pipeline/engines/surya_layout.py` | `LayoutAnalyzer` → `LayoutEngine` |
| `src/ocr_pipeline/engines/vlm_text.py` | Qwen/GLM `TextEngine` |
| `src/ocr_pipeline/engines/vlm_formula.py` | Qwen/GLM `FormulaEngine` |
| `src/ocr_pipeline/engines/ppocr_text.py` | PP-OCR Traditional text engine |
| `src/ocr_pipeline/engines/got_formula.py` | GOT-OCR 2.0 formula engine |
| `src/ocr_pipeline/engines/doclayout_yolo.py` | DocLayout-YOLO layout engine |
| `src/ocr_pipeline/engines/mineru_layout.py` | MinerU layout engine |
| `src/ocr_pipeline/engines/unimernet_formula.py` | UniMERNet formula engine |
| `src/ocr_pipeline/engines/__init__.py` | Public exports |
| `src/ocr_pipeline/factory.py` | Build engines from config |
| `src/ocr_pipeline/routers.py` | Route via `TextEngine` / `FormulaEngine` |
| `src/ocr_pipeline/pipeline.py` | Call `LayoutEngine`; optional skip polish; timing; output tag |
| `config/ocr_pipeline.yaml` | `engines:` block + `skip_polish` + `output_tag` |
| `tests/test_engines_contract.py` | Fake engines + protocol tests |
| `tests/test_engines_pipeline_smoke.py` | skip_polish + engine duck-typing smoke |
| `docs/superpowers/evals/p-ocr-branch-scorecard.md` | Human D scorecard + timing log template |
| `requirements-got-ppocr.txt` / `requirements-mineru-ppocr.txt` | Optional branch deps |

---

### Task 1: Engine protocols + fail-loud error type

**Files:**
- Create: `src/ocr_pipeline/engines/__init__.py`
- Create: `src/ocr_pipeline/engines/base.py`
- Test: `tests/test_engines_contract.py`

**Interfaces:**
- Produces: `LayoutEngine`, `TextEngine`, `FormulaEngine` protocols; `EngineError`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engines_contract.py
from __future__ import annotations

from pathlib import Path

from ocr_pipeline.engines.base import EngineError, FormulaEngine, LayoutEngine, TextEngine
from ocr_pipeline.models import BlockType, BBox, LayoutBlock


class FakeLayout:
    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]:
        return [
            LayoutBlock(
                block_id=f"p{page}_b0",
                block_type=BlockType.TEXT,
                bbox=BBox(0, 0, 10, 10),
                order=0,
                page=page,
                image_path=image_path,
            )
        ]

    def release(self) -> None:
        return None


class FakeText:
    def ocr(self, crop_path: Path) -> str:
        return "hello $x$"


class FakeFormula:
    def ocr(self, crop_path: Path) -> str:
        return "$$\nx\n$$"


def test_fakes_satisfy_protocols():
    assert isinstance(FakeLayout(), LayoutEngine)
    assert isinstance(FakeText(), TextEngine)
    assert isinstance(FakeFormula(), FormulaEngine)


def test_engine_error_is_runtime_error():
    err = EngineError("missing paddleocr")
    assert isinstance(err, RuntimeError)
    assert "paddleocr" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_engines_contract.py -q`  
Expected: FAIL (`ocr_pipeline.engines.base` missing)

- [ ] **Step 3: Write minimal implementation**

```python
# src/ocr_pipeline/engines/base.py
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ocr_pipeline.models import LayoutBlock


class EngineError(RuntimeError):
    """Missing dependency / weights / hard engine failure (fail loud)."""


@runtime_checkable
class LayoutEngine(Protocol):
    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]: ...

    def release(self) -> None: ...


@runtime_checkable
class TextEngine(Protocol):
    def ocr(self, crop_path: Path) -> str: ...


@runtime_checkable
class FormulaEngine(Protocol):
    def ocr(self, crop_path: Path) -> str: ...
```

```python
# src/ocr_pipeline/engines/__init__.py
from .base import EngineError, FormulaEngine, LayoutEngine, TextEngine

__all__ = ["EngineError", "LayoutEngine", "TextEngine", "FormulaEngine"]
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ocr_pipeline/engines tests/test_engines_contract.py
git commit -m "feat: add Layout/Text/Formula engine protocols for P-ocr"
```

---

### Task 2: Stage timer helper (logged, not scored)

**Files:**
- Create: `src/ocr_pipeline/engines/timing.py`
- Modify: `tests/test_engines_contract.py`

**Interfaces:**
- Produces: `StageTimer.section(name)` / `as_dict() -> dict[str, float]` including `total`

- [ ] **Step 1: Write the failing test**

```python
import time
from ocr_pipeline.engines.timing import StageTimer

def test_stage_timer_records_seconds():
    t = StageTimer()
    with t.section("layout"):
        time.sleep(0.01)
    d = t.as_dict()
    assert d["layout"] >= 0.01
    assert "total" in d
```

- [ ] **Step 2: Run — expect FAIL (import)**

- [ ] **Step 3: Implement**

```python
# src/ocr_pipeline/engines/timing.py
from __future__ import annotations

import time
from contextlib import contextmanager


class StageTimer:
    def __init__(self) -> None:
        self._stages: dict[str, float] = {}
        self._t0 = time.perf_counter()

    @contextmanager
    def section(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self._stages[name] = self._stages.get(name, 0.0) + (
                time.perf_counter() - start
            )

    def as_dict(self) -> dict[str, float]:
        out = dict(self._stages)
        out["total"] = time.perf_counter() - self._t0
        return out
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ocr_pipeline/engines/timing.py tests/test_engines_contract.py
git commit -m "feat: add StageTimer for logged (unscored) OCR timings"
```

---

### Task 3: Wrap existing Surya/VLM as engines

**Files:**
- Create: `src/ocr_pipeline/engines/surya_layout.py`
- Create: `src/ocr_pipeline/engines/vlm_text.py`
- Create: `src/ocr_pipeline/engines/vlm_formula.py`
- Test: extend `tests/test_engines_contract.py`

**Interfaces:**
- Consumes: `LayoutAnalyzer.analyze_page` / `release`; `VlmClient.generate`; `normalize_display_math`
- Produces: `SuryaLayoutEngine`, `VlmTextEngine`, `VlmFormulaEngine`

- [ ] **Step 1: Write failing wrapper tests**

```python
from ocr_pipeline.engines.surya_layout import SuryaLayoutEngine
from ocr_pipeline.engines.vlm_text import VlmTextEngine
from ocr_pipeline.engines.vlm_formula import VlmFormulaEngine

def test_surya_layout_engine_delegates(tmp_path):
    calls = {}

    class FakeAnalyzer:
        def analyze_page(self, image_path, page):
            calls["page"] = page
            return []

        def release(self):
            calls["released"] = True

    eng = SuryaLayoutEngine(FakeAnalyzer())
    img = tmp_path / "p.png"
    img.write_bytes(b"x")
    assert eng.analyze(img, 1) == []
    eng.release()
    assert calls["released"] is True


def test_vlm_text_engine_calls_generate(tmp_path):
    class FakeVlm:
        def generate(self, prompt, image_path=None, *, max_new_tokens=None):
            return "正文"

    crop = tmp_path / "c.png"
    crop.write_bytes(b"x")
    assert VlmTextEngine(FakeVlm()).ocr(crop) == "正文"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement wrappers**

```python
# src/ocr_pipeline/engines/surya_layout.py
from __future__ import annotations

from pathlib import Path

from ocr_pipeline.models import LayoutBlock


class SuryaLayoutEngine:
    def __init__(self, analyzer) -> None:
        self._analyzer = analyzer

    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]:
        return self._analyzer.analyze_page(image_path, page)

    def release(self) -> None:
        self._analyzer.release()
```

```python
# src/ocr_pipeline/engines/vlm_text.py
from __future__ import annotations

from pathlib import Path

from ocr_pipeline.prompts import TEXT_ROUTER_PROMPT


class VlmTextEngine:
    def __init__(self, vlm, *, max_new_tokens: int | None = None, prompt: str | None = None) -> None:
        self.vlm = vlm
        self.max_new_tokens = max_new_tokens
        self.prompt = prompt or TEXT_ROUTER_PROMPT

    def ocr(self, crop_path: Path) -> str:
        return self.vlm.generate(
            self.prompt, image_path=crop_path, max_new_tokens=self.max_new_tokens
        ).strip()
```

```python
# src/ocr_pipeline/engines/vlm_formula.py
from __future__ import annotations

from pathlib import Path

from ocr_pipeline.prompts import MATH_ROUTER_PROMPT
from ocr_pipeline.routers import normalize_display_math


class VlmFormulaEngine:
    def __init__(self, vlm, *, max_new_tokens: int | None = None) -> None:
        self.vlm = vlm
        self.max_new_tokens = max_new_tokens

    def ocr(self, crop_path: Path) -> str:
        raw = self.vlm.generate(
            MATH_ROUTER_PROMPT, image_path=crop_path, max_new_tokens=self.max_new_tokens
        )
        return normalize_display_math(raw)
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ocr_pipeline/engines tests/test_engines_contract.py
git commit -m "feat: wrap Surya and VLM clients as P-ocr engines"
```

---

### Task 4: Wire factory + router + pipeline to engines

**Files:**
- Modify: `src/ocr_pipeline/factory.py`
- Modify: `src/ocr_pipeline/routers.py`
- Modify: `src/ocr_pipeline/pipeline.py`
- Modify: `config/ocr_pipeline.yaml`
- Modify: `run_ocr_pipeline.py` (optional `--output-tag` / `--skip-polish`)
- Test: `tests/test_engines_pipeline_smoke.py`

**Interfaces:**
- `PipelineManager` takes `image_source` (needs `pdf_to_images`) + `layout_engine` (`analyze`/`release`) OR a combined object that provides both (Surya path: same `LayoutAnalyzer` for images + wrapped engine).
- Preferred: keep current `self.layout` as `LayoutAnalyzer` for `pdf_to_images`, add `self.layout_engine` for detect/release; factory sets both from the same analyzer when `engines.layout: surya`.
- `skip_polish: true` → do not call `polisher.polish`; feed draft into content-first.
- Print `TIMING: …` from `StageTimer.as_dict()` at end (logged only).
- `output_tag` prefixes artifact stem: `123.got-ppocr.tex`.

Config addition:

```yaml
engines:
  layout: surya          # surya | doclayout_yolo | mineru
  text: vlm              # vlm | ppocr
  formula: vlm           # vlm | got | unimernet
pipeline:
  skip_polish: false
  output_tag: ""
  single_instance_lock: true
```

- [ ] **Step 1: Write smoke test**

```python
# tests/test_engines_pipeline_smoke.py
from pathlib import Path

from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.cli_report import WarnCollector
from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.pipeline import PipelineManager


class ImageSource:
    def pdf_to_images(self, pdf_path, out_dir, *, limit=0):
        out_dir.mkdir(parents=True, exist_ok=True)
        page = out_dir / "page_001.png"
        page.write_bytes(b"x")
        return [page]


class LayoutEngine:
    def analyze(self, image_path, page):
        return [
            LayoutBlock("b0", BlockType.TEXT, BBox(0, 0, 10, 10), 0, page, image_path)
        ]

    def release(self):
        pass


class Router:
    def route_page(self, blocks):
        for b in blocks:
            b.raw_text = "hi"
        return blocks


class Assembler:
    def stitch(self, blocks):
        return "hi"


class BoomPolisher:
    def polish(self, draft):
        raise AssertionError("skip_polish must not call polish")

    @staticmethod
    def extract_tex_body(tex):
        return FinalPolisher.extract_tex_body(tex)

    @staticmethod
    def wrap_tex(body):
        return FinalPolisher.wrap_tex(body)


def test_skip_polish_uses_draft(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    mgr = PipelineManager(
        layout=ImageSource(),  # after Task 4, ctor may be (image_source, layout_engine, ...)
        layout_engine=LayoutEngine(),
        router=Router(),
        assembler=Assembler(),
        polisher=BoomPolisher(),
        output_dir=tmp_path / "out",
        pages_dir=tmp_path / "pages",
    )
    result = mgr.run(
        pdf,
        skip_polish=True,
        single_instance_lock=False,
        output_tag="t",
        warns=WarnCollector(),
    )
    assert result.tex_path is not None
    assert "t" in result.tex_path.name
```

Adjust constructor signature in the test to match the implementation chosen in Step 3 (document the final signature in the commit message).

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement factory/router/pipeline wiring**

Router change sketch:

```python
# MathRouter.process → self.formula_engine.ocr(block.crop_path)
# TextRouter.process → pick TABLE vs TEXT prompt, then self.text_engine.ocr(...)
```

Factory: unknown `engines.*` value → `raise EngineError(...)`.

- [ ] **Step 4: Run**

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m pytest tests/test_engines_contract.py tests/test_engines_pipeline_smoke.py tests/test_content_first_pipeline.py tests/test_polish_strategy.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: wire PipelineManager to pluggable engines and skip_polish"
```

---

### Task 5: Create `qwen-vl` snapshot branch

- [ ] **Step 1: Confirm Tasks 1–4 are on `main`**

- [ ] **Step 2: Create branch**

```powershell
git branch qwen-vl
git checkout qwen-vl
```

- [ ] **Step 3: Set branch config**

```yaml
engines: { layout: surya, text: vlm, formula: vlm }
pipeline: { skip_polish: false, output_tag: "qwen-vl" }
```

- [ ] **Step 4: Commit on branch**

```bash
git add config/ocr_pipeline.yaml
git commit -m "chore: qwen-vl branch config snapshot for P-ocr comparison"
```

- [ ] **Step 5: Return to main**

```powershell
git checkout main
```

---

### Task 6: PP-OCR text engine (shared by GOT + MinerU)

**Files:**
- Create: `src/ocr_pipeline/engines/ppocr_text.py`
- Create: `requirements-ppocr.txt` (`paddleocr` + paddlepaddle CUDA pin chosen at install time)
- Test: `tests/test_ppocr_text_engine.py` (mock OCR)

**Interfaces:**
- `PpocrTextEngine(lang=...).ocr(crop) -> str`
- Missing import → `EngineError` with install hint (no Qwen fallback)

- [ ] **Step 1: Failing mocked tests**

```python
def test_ppocr_engine_joins_lines(tmp_path, monkeypatch):
    class FakeOCR:
        def __init__(self, **kwargs):
            pass

        def ocr(self, path, cls=True):
            return [[[[0, 0], [1, 0], [1, 1], [0, 1]], ("繁中", 0.99)]]

    import ocr_pipeline.engines.ppocr_text as mod

    monkeypatch.setattr(mod, "_load_paddle_ocr", lambda **kw: FakeOCR())
    eng = mod.PpocrTextEngine(lang="chinese_cht")
    p = tmp_path / "c.png"
    p.write_bytes(b"x")
    assert "繁中" in eng.ocr(p)
```

Verify the Traditional Chinese lang code against the installed PaddleOCR version at implementation time (`chinese_cht` vs docs’ current enum) and lock one constant.

- [ ] **Step 2–4: Implement, PASS, commit**

```bash
git commit -m "feat: add PP-OCR Traditional Chinese TextEngine"
```

---

### Task 7: `got-ppocr` engines + branch

**Files:**
- Create: `src/ocr_pipeline/engines/doclayout_yolo.py`
- Create: `src/ocr_pipeline/engines/got_formula.py`
- Create: `requirements-got-ppocr.txt`
- Branch config: `engines.layout=doclayout_yolo`, `text=ppocr`, `formula=got`, `skip_polish=true`, `output_tag=got-ppocr`

**Install notes (verify when executing):**
- `pip install doclayout-yolo` + DocLayout-YOLO weights from opendatalab releases
- GOT via `transformers` + model `stepfun-ai/GOT-OCR2_0` (or HF GOT-OCR-2.0-hf variant)
- Reuse `PpocrTextEngine`

Map DocLayout labels → `BlockType` (`formula`→FORMULA, `title`→TITLE, `table`→TABLE, plain text→TEXT, else OTHER).

- [ ] **Step 1: Unit tests with fakes (CPU)**

- [ ] **Step 2: Implement engines + factory keys**

- [ ] **Step 3: Create branch + config**

```powershell
git checkout -b got-ppocr
```

- [ ] **Step 4: GPU smoke**

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe run_ocr_pipeline.py data\sources\123.pdf --limit 1 --reuse-images --check-compile
```

Expect tagged outputs + `TIMING:` line; no Qwen Stage3 load.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: got-ppocr engines (DocLayout-YOLO + PP-OCR + GOT-OCR2)"
```

---

### Task 8: `mineru-ppocr` engines + branch

**Files:**
- Create: `src/ocr_pipeline/engines/mineru_layout.py`
- Create: `src/ocr_pipeline/engines/unimernet_formula.py`
- Create: `requirements-mineru-ppocr.txt`
- Branch: `skip_polish: true`, `output_tag: mineru-ppocr`

Stack (corrected): **MinerU layout** + **UniMERNet formula** + **PP-OCR text**.

- [ ] **Step 1: Mocked unit tests**

- [ ] **Step 2: Implement with fail-loud imports**

- [ ] **Step 3: Branch + limit-1 smoke**

```powershell
git checkout main
git checkout -b mineru-ppocr
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: mineru-ppocr engines (MinerU layout + PP-OCR + UniMERNet)"
```

---

### Task 9: GLM weights cleanup (code kept)

**Files:**
- Modify: `src/ocr_pipeline/glm_client.py` docstring → deprecated
- Modify: `config/ocr_pipeline.yaml` `glm:` comment
- Create: `scripts/cleanup_glm_weights.ps1` (dry-run by default; `-Confirm` deletes HF cache for `zai-org/GLM-4.6V-Flash` only)

- [ ] **Step 1: Script dry-run prints paths**

- [ ] **Step 2: User may run with `-Confirm` later**

- [ ] **Step 3: Commit script + deprecation notes only**

```bash
git commit -m "chore: deprecate GLM in-tree; add weight cleanup script"
```

Do **not** delete `glm_client.py` here.

---

### Task 10: Comparison scorecard + planning docs

**Files:**
- Create: `docs/superpowers/evals/p-ocr-branch-scorecard.md`
- Modify: `handoff.md`, `progress.md`, `task_plan.md`

| Branch | Formula edits (score) | Prose edit min (score) | Compile (score) | Notes | layout_s (log) | text_s | formula_s | total_s |
|--------|----------------------|------------------------|-----------------|-------|----------------|--------|-----------|---------|
| qwen-vl | | | | | | | | |
| got-ppocr | | | | | | | | |
| mineru-ppocr | | | | | | | | |

- [ ] **Step 1: Write scorecard template**

- [ ] **Step 2: Point handoff/progress/task_plan at plan + scorecard**

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: add P-ocr branch comparison scorecard (speed logged only)"
```

---

## Spec coverage

| Spec requirement | Task(s) |
|------------------|---------|
| Plugin interfaces | 1, 3, 4 |
| Shared content-first contract | 4 |
| skip Stage3 on experiment branches | 4, 7, 8 |
| GOT formula + PP-OCR text + content-first | 6, 7 |
| MinerU layout + UniMERNet formula + PP-OCR | 6, 8 |
| Timing logged, not scored | 2, 4, 10 |
| Fail loud | 1, 6–8 |
| qwen / got / mineru branches | 5, 7, 8 |
| GLM weights first | 9 |
| Output tags | 4 |
| Single-instance lock | 4 (preserve) |
| D scorecard | 10 |

## Out of scope

- P-ocr Chat UI
- Second vector DB
- Full uv/torch migration
- Full-page GOT polish
- Deleting `glm_client.py` (after branches stable)
