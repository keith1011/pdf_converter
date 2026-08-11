### Task 1: PageIR figure model + render + JSON field

**Files:**
- Modify: `src/ocr_pipeline/models.py`
- Modify: `src/ocr_pipeline/content_first.py`
- Test: `tests/test_page_ir_models.py`
- Test: `tests/test_content_first.py`

**Interfaces:**
- Consumes: existing `ContentSegment`, `SegmentKind`, `write_pageir_json`, `render_page_ir`
- Produces: `SegmentKind.FIGURE`; `ContentSegment.crop_relpath: str | None = None`; JSON key `crop_relpath`; txt/tex line `(圖: {text})`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_page_ir_models.py`:

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

Append to `tests/test_content_first.py`:

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

Run: `uv run pytest tests/test_page_ir_models.py::test_content_segment_figure_has_crop_relpath tests/test_content_first.py::test_render_figure_as_caption_stub tests/test_content_first.py::test_write_pageir_json_includes_crop_relpath -q`

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

Run: `uv run pytest tests/test_page_ir_models.py tests/test_content_first.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add src/ocr_pipeline/models.py src/ocr_pipeline/content_first.py tests/test_page_ir_models.py tests/test_content_first.py
git commit -m "feat: pageir figure kind and crop_relpath"
```

---
