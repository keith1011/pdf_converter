# Task 4 Report — Wire factory, router, and pipeline to engines

## Status

Complete. The default factory now instantiates the existing Surya and VLM engine wrappers and supplies them to the pipeline and routers.

## Implementation

- Added `engines.layout`, `engines.text`, and `engines.formula` configuration. Only the implemented `surya`/`vlm` choices are accepted; unsupported names raise `EngineError`.
- `build_default_pipeline()` uses one `LayoutAnalyzer` for `pdf_to_images` and `SuryaLayoutEngine(analyzer)` for `analyze`/`release`.
- `MathRouter` delegates to `FormulaEngine.ocr(crop)` and `TextRouter` delegates to text/table `TextEngine.ocr(crop)`. A dedicated table `VlmTextEngine` keeps `TABLE_ROUTER_PROMPT`.
- Added CLI/config/run support for `skip_polish` and `output_tag`. Skipping polish wraps and sanitizes stitched drafts; tags produce `<source>.<tag>.tex`, `.txt`, and `.pageir.json`.
- Added layout, route, polish-or-skip, and finalize `StageTimer` sections plus one `TIMING:` log line.

## Final PipelineManager signature

```python
PipelineManager(
    layout,
    router,
    assembler,
    polisher,
    output_dir=Path("output"),
    pages_dir=Path("data/pdf_pages"),
    *,
    layout_engine=None,
)
```

`layout` must provide `pdf_to_images`. With `layout_engine=None`, the legacy combined layout object must provide `analyze_page` and `release`.

## TDD evidence

1. Added `tests/test_engines_pipeline_smoke.py`; before implementation, its new `layout_engine`, `skip_polish`, and `output_tag` interface was unsupported.
2. Test execution initially could not start under the Windows workspace sandbox (`workspace_readwrite` unsupported); reran with the required unrestricted local execution permission.
3. Passed:

```text
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_engines_contract.py tests/test_engines_pipeline_smoke.py tests/test_content_first_pipeline.py tests/test_polish_strategy.py tests/test_layout_artifact.py tests/test_review_fixes.py tests/test_vlm_greedy_decode.py -q
20 passed in 1.76s
```

## Scope

No GOT, PP-OCR, UniMERNet, MinerU, or DocLayout implementation was added. No `homelab` files are included.
