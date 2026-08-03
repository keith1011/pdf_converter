# Figure caption + batch publish/ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver figure crop+Qwen caption into pageir/DONE/Qdrant (`pageir_v2`) and a batch CLI that stages→publishes→ingests local `3.分析結果/output/` docs.

**Architecture:** Keep content-first finalize for prose/math. After Stage2 layout blocks exist, always crop FIGURE blocks; caption with Qwen; write `figures/<block_id>.png` beside artifacts; merge `SegmentKind.FIGURE` segments (with `crop_relpath`) into PageIR before write. Extend publish to copy `figures/` into the job; ingest embeds caption text and stores `crop_path`; batch CLI loops doc ids with fail-continue.

**Tech Stack:** Existing `ocr_pipeline` + `2_生產線/homelab/ingest` (DONE schema 1), pytest, `uv run`, Qwen2.5-VL via `VlmClient.generate`, Qdrant writer on A.

**Spec:** `3.分析結果/docs/superpowers/specs/2026-07-24-trunk-qwen-ingest-contract-design.md`

## Global Constraints

- Product is **P-ocr**; OCR is feedstock only (no Chat / ColPali in this plan).
- Trunk: MinerU layout + Qwen text/formula/captions; formula knives opt-in only.
- DONE stays **`done_schema: 1`**; bump ingest **`chunk_version` → `pageir_v2`** only for new writes.
- Collection remains **`exam_segments_v1`**.
- Figure extract when layout emits `FIGURE` (both doc types); caption Traditional Chinese.
- Caption/crop failure for one figure: warn + skip that segment; keep doc artifacts.
- Batch: preflight Z: + writer key; per-doc errors continue unless `--fail-fast`.
- Commits: only when the user explicitly asks (repo rule); otherwise stop after green tests.
- Tests: `uv run pytest <paths> -q` (repo uses uv + `pythonpath = ["src"]`).

## File map

| Path | Responsibility |
|------|----------------|
| `2_生產線/src/ocr_pipeline/models.py` | `SegmentKind.FIGURE`; `ContentSegment.crop_relpath` |
| `2_生產線/src/ocr_pipeline/content_first.py` | Serialize `crop_relpath`; render `(圖: …)`; merge figure segments in finalize |
| `2_生產線/src/ocr_pipeline/prompts.py` | `FIGURE_CAPTION_PROMPT` |
| `2_生產線/src/ocr_pipeline/figure_export.py` | Crop→`figures/`, caption via VLM, build figure `ContentSegment`s |
| `2_生產線/src/ocr_pipeline/routers.py` | Always crop FIGURE; `skip_figures` only skips draft OCR stitch |
| `2_生產線/src/ocr_pipeline/pipeline.py` | Call figure export; pass figures into finalize |
| `2_生產線/src/ocr_pipeline/factory.py` | Wire `extract_figures` from config |
| `2_生產線/src/ocr_pipeline/job_stage.py` | Build flat staging dir: `{doc}.txt/.tex/.pageir.json` + `figures/*` |
| `2_生產線/src/ocr_pipeline/batch_export.py` | CLI: docs → stage → publish → ingest |
| `2_生產線/config/ocr_pipeline.yaml` | `extract_figures: true`; clarify `skip_figures` |
| `2_生產線/homelab/ingest/publish.py` | Publish from staged dir including `figures/` |
| `2_生產線/homelab/ingest/done.py` | If `figures/` files exist on disk, require them in artifacts |
| `2_生產線/homelab/ingest/ingest.py` | `CHUNK_VERSION=pageir_v2`; payload `crop_path` for figure kind |
| `2_生產線/tests/test_page_ir_models.py` | FIGURE + crop_relpath |
| `2_生產線/tests/test_content_first.py` | Render + JSON round-trip for figures |
| `2_生產線/tests/test_figure_export.py` | Caption/crop/skip-on-error (mocked VLM) |
| `2_生產線/tests/test_skip_figures_router.py` | Update: skip_figures still crops |
| `2_生產線/tests/test_job_stage.py` | Staging layout |
| `2_生產線/tests/test_done_schema.py` | Nested `figures/` artifact |
| `2_生產線/tests/test_ingest_figures.py` | Mocked load_segments / payload fields |
| `2_生產線/tests/test_batch_export.py` | Call order + continue-on-error |

---

### Task 1: PageIR figure model + render + JSON field

**Files:**
- Modify: `2_生產線/src/ocr_pipeline/models.py`
- Modify: `2_生產線/src/ocr_pipeline/content_first.py`
- Test: `2_生產線/tests/test_page_ir_models.py`
- Test: `2_生產線/tests/test_content_first.py`

**Interfaces:**
- Consumes: existing `ContentSegment`, `SegmentKind`, `write_pageir_json`, `render_page_ir`
- Produces: `SegmentKind.FIGURE`; `ContentSegment.crop_relpath: str | None = None`; JSON key `crop_relpath`; txt/tex line `(圖: {text})`

- [ ] **Step 1: Write the failing tests**

Append to `2_生產線/tests/test_page_ir_models.py`:

```python
def test_content_segment_figure_has_crop_relpath():
    seg = ContentSegment(
        kind=SegmentKind.FIGURE,
        text="圓形面積示意圖",
        source_block_id="p001_b012",
        bbox=BBox(1, 2, 3, 4),
        crop_relpath="figures/p001_b012.png",
    )
    assert seg.kind is SegmentKind.FIGURE
    assert seg.crop_relpath == "figures/p001_b012.png"
```

Append to `2_生產線/tests/test_content_first.py`:

```python
def test_render_figure_as_caption_stub():
    page = PageIR(
        page_index=1,
        segments=[
            ContentSegment(
                kind=SegmentKind.FIGURE,
                text="圓形面積示意圖",
                source_block_id="p001_b012",
                bbox=BBox(0, 0, 10, 10),
                crop_relpath="figures/p001_b012.png",
            )
        ],
    )
    txt, tex_body = render_page_ir(page)
    assert txt == "(圖: 圓形面積示意圖)"
    assert tex_body == "(圖: 圓形面積示意圖)"


def test_write_pageir_json_includes_crop_relpath(tmp_path: Path):
    pages = [
        PageIR(
            page_index=1,
            segments=[
                ContentSegment(
                    kind=SegmentKind.FIGURE,
                    text="示意圖",
                    source_block_id="p001_b012",
                    bbox=BBox(0, 0, 10, 10),
                    crop_relpath="figures/p001_b012.png",
                )
            ],
        )
    ]
    path = tmp_path / "demo.pageir.json"
    write_pageir_json(path, pages)
    data = json.loads(path.read_text(encoding="utf-8"))
    seg = data["pages"][0]["segments"][0]
    assert seg["kind"] == "figure"
    assert seg["crop_relpath"] == "figures/p001_b012.png"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest 2_生產線/tests/test_page_ir_models.py::test_content_segment_figure_has_crop_relpath 2_生產線/tests/test_content_first.py::test_render_figure_as_caption_stub 2_生產線/tests/test_content_first.py::test_write_pageir_json_includes_crop_relpath -q`

Expected: FAIL (`FIGURE` missing and/or `crop_relpath` missing)

- [ ] **Step 3: Minimal implementation**

In `models.py`:

```python
class SegmentKind(str, Enum):
    PROSE = "prose"
    MATH = "math"
    MARK_NOTE = "mark_note"
    FIGURE = "figure"


@dataclass
class ContentSegment:
    kind: SegmentKind
    text: str
    source_block_id: str
    bbox: BBox
    integrity: IntegrityStatus = IntegrityStatus.OK
    crop_relpath: str | None = None
```

In `content_first.py` `render_page_ir`, add before the final `else`:

```python
        elif seg.kind is SegmentKind.FIGURE:
            lines.append(f"(圖: {seg.text})")
```

In `write_pageir_json` segment dict, add:

```python
                        "crop_relpath": s.crop_relpath,
```

In `apply_integrity_to_page`, when rebuilding MATH segments, pass `crop_relpath=seg.crop_relpath` (always `None` for math today).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest 2_生產線/tests/test_page_ir_models.py 2_生產線/tests/test_content_first.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add 2_生產線/src/ocr_pipeline/models.py 2_生產線/src/ocr_pipeline/content_first.py 2_生產線/tests/test_page_ir_models.py 2_生產線/tests/test_content_first.py
git commit -m "feat: pageir figure kind and crop_relpath"
```

---

### Task 2: Figure caption prompt + `figure_export` helper

**Files:**
- Modify: `2_生產線/src/ocr_pipeline/prompts.py`
- Create: `2_生產線/src/ocr_pipeline/figure_export.py`
- Test: `2_生產線/tests/test_figure_export.py`

**Interfaces:**
- Consumes: `LayoutBlock`, `BlockType.FIGURE`, `VlmClient.generate(prompt, image_path=, max_new_tokens=)`, `FIGURE_CAPTION_PROMPT`
- Produces:
  - `FIGURE_CAPTION_PROMPT: str`
  - `def export_figures(*, blocks: list[LayoutBlock], figures_dir: Path, vlm, max_new_tokens: int = 128) -> tuple[list[ContentSegment], list[str]]`
  - Writes `figures_dir / f"{block.block_id}.png"`; returns segments with `crop_relpath=f"figures/{block.block_id}.png"`; warnings on per-figure failure

- [ ] **Step 1: Write the failing test**

```python
# 2_生產線/tests/test_figure_export.py
from __future__ import annotations

from pathlib import Path

from PIL import Image

from ocr_pipeline.figure_export import export_figures
from ocr_pipeline.models import BBox, BlockType, LayoutBlock, SegmentKind


class FakeVlm:
    def generate(self, prompt, image_path=None, max_new_tokens=None):
        assert image_path is not None
        assert "圖" in prompt or "caption" in prompt.lower() or "說明" in prompt
        return "圓形面積示意圖"


def test_export_figures_writes_png_and_segment(tmp_path: Path):
    page = tmp_path / "page.png"
    Image.new("RGB", (40, 40), color=(200, 200, 200)).save(page)
    block = LayoutBlock(
        "p001_b012",
        BlockType.FIGURE,
        BBox(2, 2, 20, 20),
        0,
        1,
        page,
        crop_path=None,
    )
    figures_dir = tmp_path / "figures"
    segs, warns = export_figures(blocks=[block], figures_dir=figures_dir, vlm=FakeVlm())
    assert warns == []
    assert len(segs) == 1
    assert segs[0].kind is SegmentKind.FIGURE
    assert segs[0].text == "圓形面積示意圖"
    assert segs[0].crop_relpath == "figures/p001_b012.png"
    assert (figures_dir / "p001_b012.png").is_file()


class BoomVlm:
    def generate(self, prompt, image_path=None, max_new_tokens=None):
        raise RuntimeError("cuda boom")


def test_export_figures_skips_failed_caption(tmp_path: Path):
    page = tmp_path / "page.png"
    Image.new("RGB", (40, 40), color=(200, 200, 200)).save(page)
    block = LayoutBlock(
        "p001_b099",
        BlockType.FIGURE,
        BBox(2, 2, 20, 20),
        0,
        1,
        page,
    )
    segs, warns = export_figures(
        blocks=[block], figures_dir=tmp_path / "figures", vlm=BoomVlm()
    )
    assert segs == []
    assert any("p001_b099" in w for w in warns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest 2_生產線/tests/test_figure_export.py -q`

Expected: FAIL (`figure_export` missing)

- [ ] **Step 3: Minimal implementation**

Add to `prompts.py`:

```python
FIGURE_CAPTION_PROMPT = """你正在看一張試卷／講義中的圖（圖表、幾何圖、示意圖）。

任務：用一句繁體中文短說明這張圖畫什麼（供題庫檢索）。
規則：
- 只輸出一句話，不要編號、不要 markdown、不要「這張圖是」。
- 不要發明圖中沒有的細節；看不清就寫「圖示（細節不清）」。
"""
```

Create `figure_export.py`:

```python
from __future__ import annotations

from pathlib import Path

from .models import (
    BBox,
    BlockType,
    ContentSegment,
    IntegrityStatus,
    LayoutBlock,
    SegmentKind,
)
from .prompts import FIGURE_CAPTION_PROMPT


def _ensure_crop(block: LayoutBlock, figures_dir: Path) -> Path:
    figures_dir.mkdir(parents=True, exist_ok=True)
    dest = figures_dir / f"{block.block_id}.png"
    if block.crop_path is not None and block.crop_path.is_file():
        dest.write_bytes(block.crop_path.read_bytes())
        return dest
    from PIL import Image

    with Image.open(block.image_path) as im:
        image = im.convert("RGB")
        image.load()
        w, h = image.size
        box = block.bbox.clamp(w, h).as_int_tuple()
        crop = image.crop(box)
    crop.save(dest)
    return dest


def export_figures(
    *,
    blocks: list[LayoutBlock],
    figures_dir: Path,
    vlm,
    max_new_tokens: int = 128,
) -> tuple[list[ContentSegment], list[str]]:
    segments: list[ContentSegment] = []
    warnings: list[str] = []
    for block in blocks:
        if block.block_type is not BlockType.FIGURE:
            continue
        try:
            crop_path = _ensure_crop(block, figures_dir)
            caption = vlm.generate(
                FIGURE_CAPTION_PROMPT,
                image_path=crop_path,
                max_new_tokens=max_new_tokens,
            ).strip()
            if not caption:
                raise RuntimeError("empty caption")
            segments.append(
                ContentSegment(
                    kind=SegmentKind.FIGURE,
                    text=caption,
                    source_block_id=block.block_id,
                    bbox=block.bbox,
                    integrity=IntegrityStatus.OK,
                    crop_relpath=f"figures/{block.block_id}.png",
                )
            )
        except Exception as exc:  # noqa: BLE001 — per-figure isolation
            warnings.append(f"figure {block.block_id}: {exc}")
    return segments, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest 2_生產線/tests/test_figure_export.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add 2_生產線/src/ocr_pipeline/prompts.py 2_生產線/src/ocr_pipeline/figure_export.py 2_生產線/tests/test_figure_export.py
git commit -m "feat: export figure crops and Qwen captions"
```

---

### Task 3: Router always crops FIGURE; finalize merges figure segments

**Files:**
- Modify: `2_生產線/src/ocr_pipeline/routers.py`
- Modify: `2_生產線/src/ocr_pipeline/content_first.py` (`finalize_content_first` signature)
- Modify: `2_生產線/src/ocr_pipeline/pipeline.py`
- Modify: `2_生產線/src/ocr_pipeline/factory.py`
- Modify: `2_生產線/config/ocr_pipeline.yaml`
- Test: `2_生產線/tests/test_skip_figures_router.py`
- Test: `2_生產線/tests/test_content_first.py` (merge helper)

**Interfaces:**
- Consumes: `export_figures`, `finalize_content_first`
- Produces:
  - `skip_figures=True` → still crops FIGURE, sets `raw_text=""` + `meta["skipped"]=True` (no text OCR in draft)
  - `finalize_content_first(..., figure_segments: list[ContentSegment] | None = None)` appends figures onto matching `page_index` pages (match via `source_block_id` prefix `p{page:03d}_` **or** pass `dict[int, list[ContentSegment]]`)
  - Prefer: `figure_segments_by_page: dict[int, list[ContentSegment]] | None = None`
  - Config `pipeline.extract_figures: true` (default True)

- [ ] **Step 1: Write failing tests**

Replace `test_skip_figures_true_skips_without_crop` expectations in `2_生產線/tests/test_skip_figures_router.py`:

```python
def test_skip_figures_true_crops_but_does_not_ocr(tmp_path):
    router, page = _page_and_router(tmp_path, skip_figures=True)
    block = LayoutBlock(
        "b0", BlockType.FIGURE, BBox(2, 2, 20, 20), 0, 1, page, meta={}
    )
    out = router.route_block(block)
    assert out.raw_text == ""
    assert out.meta.get("skipped") is True
    assert out.crop_path is not None
    assert out.crop_path.exists()
```

Add merge test in `2_生產線/tests/test_content_first.py`:

```python
def test_finalize_merges_figure_segments(tmp_path: Path):
    def wrap(body: str) -> str:
        return f"\\documentclass{{ctexart}}\\begin{{document}}{body}\\end{{document}}"

    fig = ContentSegment(
        kind=SegmentKind.FIGURE,
        text="示意圖",
        source_block_id="p001_b012",
        bbox=BBox(0, 0, 10, 10),
        crop_relpath="figures/p001_b012.png",
    )
    full_txt, _, txt_path, _, pageir_path, _ = finalize_content_first(
        source="demo",
        output_dir=tmp_path,
        page_drafts=[(1, "正文一行", BBox(0, 0, 100, 100))],
        wrap_tex_fn=wrap,
        figure_segments_by_page={1: [fig]},
    )
    assert "(圖: 示意圖)" in full_txt
    data = json.loads(pageir_path.read_text(encoding="utf-8"))
    kinds = [s["kind"] for s in data["pages"][0]["segments"]]
    assert "figure" in kinds
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest 2_生產線/tests/test_skip_figures_router.py::test_skip_figures_true_crops_but_does_not_ocr 2_生產線/tests/test_content_first.py::test_finalize_merges_figure_segments -q`

Expected: FAIL

- [ ] **Step 3: Minimal implementation**

`routers.py` `route_block` for FIGURE + `skip_figures`:

```python
        if block.block_type in self.FIGURE_TYPES and self.skip_figures:
            block.crop_path = self.crop(block)
            print(
                f"    skip-ocr {block.block_id} [{block.block_type.value}] "
                f"order={block.order} (skip_figures; crop kept)"
            )
            block.raw_text = ""
            block.meta["skipped"] = True
            block.meta["skip_reason"] = "skip_figures"
            return block
```

`finalize_content_first` — after building each page IR, append:

```python
    figure_segments_by_page: dict[int, list[ContentSegment]] | None = None,
...
        page, warns = build_page_ir_from_stitched(page_index, stitched_text, page_bbox)
        if figure_segments_by_page:
            extra = figure_segments_by_page.get(page_index) or []
            if extra:
                page = PageIR(
                    page_index=page.page_index,
                    segments=[*page.segments, *extra],
                )
```

`pipeline.py` after route loop (before polish is OK; caption needs VLM — run after `_release_layout`, can share Stage2/3 VLM). Recommended placement: after polish section, before finalize, using `self.polisher.vlm`:

```python
        figure_by_page: dict[int, list] = {}
        extract_figures = getattr(self, "extract_figures", True)
        if extract_figures:
            from .figure_export import export_figures

            figures_root = self.output_dir / artifact_source / "figures"
            all_blocks = [b for pr in pages for b in pr.blocks]
            segs, fig_warns = export_figures(
                blocks=all_blocks,
                figures_dir=figures_root,
                vlm=self.polisher.vlm,
            )
            for w in fig_warns:
                warns.add(w)
            for seg in segs:
                # block_id like p001_b012 → page 1
                page_no = int(seg.source_block_id.split("_")[0][1:])
                figure_by_page.setdefault(page_no, []).append(seg)
```

Pass `figure_segments_by_page=figure_by_page` into `finalize_content_first`.

`factory.py`: read `extract_figures = bool(pipe_cfg.get("extract_figures", True))` and set `manager.extract_figures = extract_figures` (or constructor kwarg).

`2_生產線/config/ocr_pipeline.yaml`:

```yaml
  # skip_figures: do not OCR figures into Stage2 draft stitch (crops still kept for caption).
  skip_figures: true
  # extract_figures: write figures/*.png + Qwen captions into pageir (ingest contract).
  extract_figures: true
```

- [ ] **Step 4: Run related tests**

Run: `uv run pytest 2_生產線/tests/test_skip_figures_router.py 2_生產線/tests/test_content_first.py 2_生產線/tests/test_figure_export.py 2_生產線/tests/test_engines_pipeline_smoke.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add 2_生產線/src/ocr_pipeline/routers.py 2_生產線/src/ocr_pipeline/content_first.py 2_生產線/src/ocr_pipeline/pipeline.py 2_生產線/src/ocr_pipeline/factory.py 2_生產線/config/ocr_pipeline.yaml 2_生產線/tests/test_skip_figures_router.py 2_生產線/tests/test_content_first.py
git commit -m "feat: wire figure export into pipeline finalize"
```

---

### Task 4: Job staging + publish copies `figures/`

**Files:**
- Create: `2_生產線/src/ocr_pipeline/job_stage.py`
- Modify: `2_生產線/homelab/ingest/publish.py`
- Modify: `2_生產線/homelab/ingest/done.py` (optional disk check for figures/)
- Test: `2_生產線/tests/test_job_stage.py`
- Test: `2_生產線/tests/test_done_schema.py`

**Interfaces:**
- Produces:
  - `def stage_job_dir(*, doc_id: str, output_dir: Path, staging_dir: Path) -> Path`
    - Copies `{doc_id}.txt` (required), `.tex`/`.pageir.json` if present
    - Copies `output_dir/{doc_id}/figures/*.png` → `staging_dir/figures/*.png`
  - `publish(..., source_dir=staging_dir)` already copies every file listed in artifacts — extend publish to discover `figures/**` under `source_dir` and add to `artifacts_src`

- [ ] **Step 1: Write failing tests**

```python
# 2_生產線/tests/test_job_stage.py
from pathlib import Path

from ocr_pipeline.job_stage import stage_job_dir


def test_stage_job_dir_copies_figures(tmp_path: Path):
    out = tmp_path / "output"
    out.mkdir()
    (out / "123.txt").write_text("hi", encoding="utf-8")
    (out / "123.pageir.json").write_text("{}", encoding="utf-8")
    fig = out / "123" / "figures"
    fig.mkdir(parents=True)
    (fig / "p001_b012.png").write_bytes(b"PNG")
    staging = tmp_path / "stage"
    dest = stage_job_dir(doc_id="123", output_dir=out, staging_dir=staging)
    assert (dest / "123.txt").is_file()
    assert (dest / "figures" / "p001_b012.png").is_file()
```

Extend `2_生產線/tests/test_done_schema.py`:

```python
def test_validate_done_with_figures_artifact(tmp_path: Path) -> None:
    txt = tmp_path / "123.txt"
    txt.write_text("hello\n", encoding="utf-8")
    fig_dir = tmp_path / "figures"
    fig_dir.mkdir()
    png = fig_dir / "p001_b012.png"
    png.write_bytes(b"x")
    data = {
        "done_schema": 1,
        "job_id": "20260724-123-001",
        "doc_id": "123",
        "created_at": "2026-07-24T00:00:00+00:00",
        "source_pdf": "123.pdf",
        "artifacts": [
            {"path": "123.txt", "sha256": sha256_file(txt)},
            {"path": "figures/p001_b012.png", "sha256": sha256_file(png)},
        ],
        "ocr_pipeline_version": "abc1234",
    }
    validate_done_dict(data, job_dir=tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest 2_生產線/tests/test_job_stage.py 2_生產線/tests/test_done_schema.py::test_validate_done_with_figures_artifact -q`

Expected: FAIL (`job_stage` missing) / PASS for done if nested paths already allowed — if done test passes early, keep it as regression lock.

- [ ] **Step 3: Minimal implementation**

`job_stage.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path


def stage_job_dir(*, doc_id: str, output_dir: Path, staging_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    staging_dir = staging_dir.resolve()
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    txt = output_dir / f"{doc_id}.txt"
    if not txt.is_file():
        raise FileNotFoundError(txt)
    shutil.copy2(txt, staging_dir / txt.name)
    for name in (f"{doc_id}.tex", f"{doc_id}.pageir.json"):
        src = output_dir / name
        if src.is_file():
            shutil.copy2(src, staging_dir / name)

    figures_src = output_dir / doc_id / "figures"
    if figures_src.is_dir():
        dest = staging_dir / "figures"
        dest.mkdir(parents=True)
        for png in sorted(figures_src.glob("*.png")):
            shutil.copy2(png, dest / png.name)
    return staging_dir
```

In `publish.py`, after collecting optional tex/pageir:

```python
    figures_dir = source_dir / "figures"
    if figures_dir.is_dir():
        for png in sorted(figures_dir.glob("*.png")):
            artifacts_src.append(png)
```

And when copying, preserve relative path under incoming:

```python
    for src in artifacts_src:
        rel = src.name if src.parent == source_dir else str(Path(src.parent.name) / src.name)
        # better:
        rel = str(src.relative_to(source_dir)).replace("\\", "/")
        dest = incoming / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        artifact_meta.append({"path": rel, "sha256": sha256_file(dest)})
```

In `done.py` after optional pageir/tex check:

```python
        figures = job_dir / "figures"
        if figures.is_dir():
            for png in figures.glob("*.png"):
                rel = f"figures/{png.name}"
                if rel not in seen:
                    raise ValueError(f"{rel} exists on disk but not listed in artifacts")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest 2_生產線/tests/test_job_stage.py 2_生產線/tests/test_done_schema.py -q`

Expected: PASS

Also smoke (no Z: required):

```python
# optional local unit using tmp share root
```

Add `2_生產線/tests/test_publish_figures.py` if needed:

```python
def test_publish_includes_figures(tmp_path: Path):
    import sys
    sys.path.insert(0, str(Path("2_生產線/homelab/ingest").resolve()))
    from publish import publish

    src = tmp_path / "src"
    src.mkdir()
    (src / "123.txt").write_text("hi", encoding="utf-8")
    (src / "figures").mkdir()
    (src / "figures" / "p001_b012.png").write_bytes(b"PNG")
    share = tmp_path / "Z"
    (share / "jobs").mkdir(parents=True)
    final = publish(doc_id="123", source_dir=src, share_root=share, job_id="t-123")
    assert (final / "figures" / "p001_b012.png").is_file()
    done = json.loads((final / "DONE.json").read_text(encoding="utf-8"))
    paths = {a["path"] for a in done["artifacts"]}
    assert "figures/p001_b012.png" in paths
```

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add 2_生產線/src/ocr_pipeline/job_stage.py 2_生產線/homelab/ingest/publish.py 2_生產線/homelab/ingest/done.py 2_生產線/tests/test_job_stage.py 2_生產線/tests/test_done_schema.py 2_生產線/tests/test_publish_figures.py
git commit -m "feat: stage and publish figure artifacts"
```

---

### Task 5: Ingest `pageir_v2` + `crop_path` payload

**Files:**
- Modify: `2_生產線/homelab/ingest/ingest.py`
- Test: `2_生產線/tests/test_ingest_figures.py`

**Interfaces:**
- Consumes: pageir segments with `kind=figure` and `crop_relpath`
- Produces: `CHUNK_VERSION = "pageir_v2"`; `load_segments` includes `crop_path` (from `crop_relpath`); payload omits `crop_path` for non-figures

- [ ] **Step 1: Write failing test**

```python
# 2_生產線/tests/test_ingest_figures.py
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "homelab" / "ingest"))

from ingest import CHUNK_VERSION, load_segments  # noqa: E402


def test_chunk_version_is_pageir_v2():
    assert CHUNK_VERSION == "pageir_v2"


def test_load_segments_includes_crop_path(tmp_path: Path):
    doc_id = "123"
    pageir = {
        "pages": [
            {
                "page_index": 1,
                "segments": [
                    {
                        "kind": "figure",
                        "text": "圓形示意圖",
                        "source_block_id": "p001_b012",
                        "bbox": [0, 0, 1, 1],
                        "integrity": "ok",
                        "crop_relpath": "figures/p001_b012.png",
                    }
                ],
            }
        ]
    }
    (tmp_path / f"{doc_id}.pageir.json").write_text(
        json.dumps(pageir), encoding="utf-8"
    )
    (tmp_path / f"{doc_id}.txt").write_text("x", encoding="utf-8")
    segs = load_segments(tmp_path, doc_id)
    assert segs[0]["kind"] == "figure"
    assert segs[0]["text"] == "圓形示意圖"
    assert segs[0]["crop_path"] == "figures/p001_b012.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest 2_生產線/tests/test_ingest_figures.py -q`

Expected: FAIL (`pageir_v1` and/or missing `crop_path`)

- [ ] **Step 3: Minimal implementation**

In `ingest.py`:

```python
CHUNK_VERSION = "pageir_v2"
```

In `load_segments` when appending from pageir:

```python
                item = {
                    "doc_id": doc_id,
                    "page": page_index,
                    "segment_id": seg_id,
                    "kind": seg.get("kind", "prose"),
                    "text": text,
                    "tex": tex,
                    "source_path": str(pageir.name),
                }
                crop = seg.get("crop_relpath")
                if crop:
                    item["crop_path"] = crop
                out.append(item)
```

In payload construction:

```python
        payload = {
            ...
            "chunk_version": CHUNK_VERSION,
            "job_id": done["job_id"],
        }
        if seg.get("crop_path"):
            payload["crop_path"] = seg["crop_path"]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest 2_生產線/tests/test_ingest_figures.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add 2_生產線/homelab/ingest/ingest.py 2_生產線/tests/test_ingest_figures.py
git commit -m "feat: ingest figure captions as pageir_v2 with crop_path"
```

---

### Task 6: Batch CLI `ocr_pipeline.batch_export`

**Files:**
- Create: `2_生產線/src/ocr_pipeline/batch_export.py`
- Test: `2_生產線/tests/test_batch_export.py`

**Interfaces:**
- Produces module CLI:
  - `uv run python -m ocr_pipeline.batch_export --docs 123,789 --output-dir output --share-root Z:/ --publish --ingest`
  - `--from-file docs.txt` (one doc_id per line)
  - `--fail-fast`
  - `--reindex` passed to ingest
  - Preflight: `share_root/jobs` writable; `QDRANT_WRITER_KEY` or `--api-key` if `--ingest`
  - Per doc: `stage_job_dir` → `publish` → `ingest_job`
  - On error: log `doc_id` + exception; continue unless `--fail-fast`
  - Exit code 1 if any doc failed

- [ ] **Step 1: Write failing test**

```python
# 2_生產線/tests/test_batch_export.py
from __future__ import annotations

from pathlib import Path

from ocr_pipeline.batch_export import run_batch


def test_batch_continues_after_one_failure(tmp_path: Path, monkeypatch):
    calls: list[str] = []

    def fake_stage(*, doc_id, output_dir, staging_dir):
        calls.append(f"stage:{doc_id}")
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / f"{doc_id}.txt").write_text("x", encoding="utf-8")
        return staging_dir

    def fake_publish(**kwargs):
        doc_id = kwargs["doc_id"]
        calls.append(f"publish:{doc_id}")
        if doc_id == "bad":
            raise RuntimeError("boom")
        return tmp_path / "jobs" / doc_id

    def fake_ingest(job_dir, **kwargs):
        calls.append(f"ingest:{job_dir.name}")
        return 1, 1

    monkeypatch.setattr("ocr_pipeline.batch_export.stage_job_dir", fake_stage)
    monkeypatch.setattr("ocr_pipeline.batch_export.publish", fake_publish)
    monkeypatch.setattr("ocr_pipeline.batch_export.ingest_job", fake_ingest)

    rc = run_batch(
        doc_ids=["bad", "good"],
        output_dir=tmp_path / "output",
        share_root=tmp_path / "Z",
        do_publish=True,
        do_ingest=True,
        fail_fast=False,
        staging_root=tmp_path / "staging",
        qdrant_url="http://example",
        api_key="k",
        reindex=False,
    )
    assert rc == 1
    assert calls == [
        "stage:bad",
        "publish:bad",
        "stage:good",
        "publish:good",
        "ingest:good",
    ]
```

Note: adjust expected call list if ingest is skipped when publish fails (correct behavior: no ingest after failed publish).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest 2_生產線/tests/test_batch_export.py -q`

Expected: FAIL (module missing)

- [ ] **Step 3: Minimal implementation**

```python
# 2_生產線/src/ocr_pipeline/batch_export.py
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from .job_stage import stage_job_dir


def _import_homelab():
    root = Path(__file__).resolve().parents[2]
    ingest_dir = root / "homelab" / "ingest"
    if str(ingest_dir) not in sys.path:
        sys.path.insert(0, str(ingest_dir))
    from ingest import ingest_job  # type: ignore
    from publish import publish  # type: ignore

    return publish, ingest_job


publish, ingest_job = _import_homelab()  # noqa: E305 — lazy at import for tests to monkeypatch


def preflight(*, share_root: Path, do_publish: bool, do_ingest: bool, api_key: str | None) -> None:
    if do_publish:
        jobs = share_root / "jobs"
        jobs.mkdir(parents=True, exist_ok=True)
        probe = jobs / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    if do_ingest and not api_key:
        raise SystemExit("Set --api-key or QDRANT_WRITER_KEY before --ingest")


def run_batch(
    *,
    doc_ids: list[str],
    output_dir: Path,
    share_root: Path,
    do_publish: bool,
    do_ingest: bool,
    fail_fast: bool,
    staging_root: Path,
    qdrant_url: str,
    api_key: str | None,
    reindex: bool,
) -> int:
    failures = 0
    for doc_id in doc_ids:
        try:
            staging = staging_root / doc_id
            stage_job_dir(doc_id=doc_id, output_dir=output_dir, staging_dir=staging)
            job_dir = None
            if do_publish:
                job_dir = publish(
                    doc_id=doc_id,
                    source_dir=staging,
                    share_root=share_root,
                )
                print(f"PUBLISHED {doc_id} -> {job_dir}")
            if do_ingest:
                if job_dir is None:
                    raise RuntimeError("--ingest requires --publish in this milestone")
                n, total = ingest_job(
                    job_dir,
                    qdrant_url=qdrant_url,
                    api_key=api_key or "",
                    reindex=reindex,
                )
                print(f"INGESTED {doc_id} {n}/{total}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"ERROR {doc_id}: {exc}")
            if fail_fast:
                return 1
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Batch stage/publish/ingest OCR output docs")
    ap.add_argument("--docs", default="", help="Comma-separated doc ids")
    ap.add_argument("--from-file", type=Path, default=None)
    ap.add_argument("--output-dir", type=Path, default=Path("output"))
    ap.add_argument("--share-root", type=Path, default=Path("Z:/"))
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL", "http://192.168.1.107:6333"))
    ap.add_argument("--api-key", default=os.environ.get("QDRANT_WRITER_KEY") or os.environ.get("QDRANT_API_KEY"))
    ap.add_argument("--staging-root", type=Path, default=None)
    args = ap.parse_args(argv)

    doc_ids: list[str] = []
    if args.docs:
        doc_ids.extend([d.strip() for d in args.docs.split(",") if d.strip()])
    if args.from_file:
        doc_ids.extend(
            [
                line.strip()
                for line in args.from_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        )
    if not doc_ids:
        raise SystemExit("Provide --docs or --from-file")

    staging_root = args.staging_root or Path(tempfile.mkdtemp(prefix="pocr-stage-"))
    preflight(
        share_root=args.share_root,
        do_publish=args.publish,
        do_ingest=args.ingest,
        api_key=args.api_key,
    )
    return run_batch(
        doc_ids=doc_ids,
        output_dir=args.output_dir,
        share_root=args.share_root,
        do_publish=args.publish,
        do_ingest=args.ingest,
        fail_fast=args.fail_fast,
        staging_root=staging_root,
        qdrant_url=args.qdrant_url,
        api_key=args.api_key,
        reindex=args.reindex,
    )


if __name__ == "__main__":
    raise SystemExit(main())
```

Fix import pattern so tests can monkeypatch `ocr_pipeline.batch_export.publish` — prefer importing inside `run_batch` from module globals that tests patch:

```python
# at module level after defining run_batch helpers:
from ocr_pipeline.job_stage import stage_job_dir as stage_job_dir  # already

# In run_batch, use globals:
# publish / ingest_job assigned in main via _import_homelab, default None
publish = None
ingest_job = None
```

Implementer: ensure `test_batch_export` monkeypatches work; call `_import_homelab()` only in `main()`, and in `run_batch` use:

```python
    pub = publish
    ing = ingest_job
    if pub is None or ing is None:
        pub, ing = _import_homelab()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest 2_生產線/tests/test_batch_export.py 2_生產線/tests/test_job_stage.py 2_生產線/tests/test_ingest_figures.py 2_生產線/tests/test_figure_export.py 2_生產線/tests/test_content_first.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add 2_生產線/src/ocr_pipeline/batch_export.py 2_生產線/tests/test_batch_export.py
git commit -m "feat: batch stage/publish/ingest CLI"
```

---

### Task 7: Planning docs + full regression

**Files:**
- Modify: `task_plan.md`, `findings.md`, `progress.md`
- Modify: `handoff.md` (batch command snippet only if present)

- [ ] **Step 1: Run full unit suite**

Run: `uv run pytest -q`

Expected: all previously passing tests still pass; new tests included

- [ ] **Step 2: Update planning memory**

In `task_plan.md` Next Action: mark figure/batch plan in progress/complete; ColPali still backlog.

In `findings.md`: note `skip_figures` = no draft OCR; `extract_figures` = caption path; `chunk_version=pageir_v2`.

In `progress.md`: dated note with test count.

- [ ] **Step 3: Manual smoke checklist (do not auto-run GPU unless user asks)**

```text
1. uv run python 2_生產線/run_ocr_pipeline.py --pdf 1_收集資料/data/sources/<doc>.pdf --limit 1
2. Confirm 3.分析結果/output/<stem>/figures/*.png and pageir figure segments
3. uv run python -m ocr_pipeline.batch_export --docs <stem> --publish --ingest --share-root Z:/
4. Qdrant: point kind=figure, crop_path set, chunk_version=pageir_v2
```

- [ ] **Step 4: Commit docs (only if user asked)**

```bash
git add task_plan.md findings.md progress.md handoff.md
git commit -m "docs: figure ingest + batch CLI status"
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Qwen caption + crop PNG | Task 2–3 |
| pageir `kind=figure` + `crop_relpath` | Task 1 |
| Linear `(圖: …)` stub | Task 1 |
| DONE schema 1 + `figures/` artifacts | Task 4 |
| Qdrant caption embed + `crop_path` + `pageir_v2` | Task 5 |
| Batch CLI from `3.分析結果/output/` with continue-on-error | Task 6 |
| Caption failure isolation | Task 2 |
| Preflight Z:/ + writer key | Task 6 |
| ColPali deferred | Global Constraints + Task 7 |
| Trunk MinerU+Qwen already locked | out of scope (done) |

## Placeholder scan

No TBD/TODO steps; commands and code are concrete. Commit steps gated on user request.

## Type consistency

- `crop_relpath` (pageir / ContentSegment) → ingest maps to payload `crop_path`
- `figures/{block_id}.png` relative paths with forward slashes
- `CHUNK_VERSION = "pageir_v2"`
- `export_figures(...) -> tuple[list[ContentSegment], list[str]]`
- `stage_job_dir(...) -> Path`
- `run_batch(...) -> int` exit code
