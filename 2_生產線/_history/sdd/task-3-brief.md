### Task 3: Router always crops FIGURE; finalize merges figure segments

**Files:**
- Modify: `src/ocr_pipeline/routers.py`
- Modify: `src/ocr_pipeline/content_first.py` (`finalize_content_first` signature)
- Modify: `src/ocr_pipeline/pipeline.py`
- Modify: `src/ocr_pipeline/factory.py`
- Modify: `config/ocr_pipeline.yaml`
- Test: `tests/test_skip_figures_router.py`
- Test: `tests/test_content_first.py` (merge helper)

**Interfaces:**
- Consumes: `export_figures`, `finalize_content_first`
- Produces:
  - `skip_figures=True` → still crops FIGURE, sets `raw_text=""` + `meta["skipped"]=True` (no text OCR in draft)
  - `finalize_content_first(..., figure_segments: list[ContentSegment] | None = None)` appends figures onto matching `page_index` pages (match via `source_block_id` prefix `p{page:03d}_` **or** pass `dict[int, list[ContentSegment]]`)
  - Prefer: `figure_segments_by_page: dict[int, list[ContentSegment]] | None = None`
  - Config `pipeline.extract_figures: true` (default True)

- [ ] **Step 1: Write failing tests**

Replace `test_skip_figures_true_skips_without_crop` expectations in `tests/test_skip_figures_router.py`:

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

Add merge test in `tests/test_content_first.py`:

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

Run: `uv run pytest tests/test_skip_figures_router.py::test_skip_figures_true_crops_but_does_not_ocr tests/test_content_first.py::test_finalize_merges_figure_segments -q`

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

`config/ocr_pipeline.yaml`:

```yaml
  # skip_figures: do not OCR figures into Stage2 draft stitch (crops still kept for caption).
  skip_figures: true
  # extract_figures: write figures/*.png + Qwen captions into pageir (ingest contract).
  extract_figures: true
```

- [ ] **Step 4: Run related tests**

Run: `uv run pytest tests/test_skip_figures_router.py tests/test_content_first.py tests/test_figure_export.py tests/test_engines_pipeline_smoke.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add src/ocr_pipeline/routers.py src/ocr_pipeline/content_first.py src/ocr_pipeline/pipeline.py src/ocr_pipeline/factory.py config/ocr_pipeline.yaml tests/test_skip_figures_router.py tests/test_content_first.py
git commit -m "feat: wire figure export into pipeline finalize"
```

---
