# Task 1 review package (uncommitted working tree)

## Note
No commits (repo rule). Diff is working-tree changes for Task 1 files only.

## Files
 src/ocr_pipeline/content_first.py |  4 ++++
 src/ocr_pipeline/models.py        |  2 ++
 tests/test_content_first.py       | 41 +++++++++++++++++++++++++++++++++++++++
 tests/test_page_ir_models.py      | 12 ++++++++++++
 4 files changed, 59 insertions(+)

## Diff
```diff

diff --git a/src/ocr_pipeline/content_first.py b/src/ocr_pipeline/content_first.py
index a88f677..8f7f5bc 100644
--- a/src/ocr_pipeline/content_first.py
+++ b/src/ocr_pipeline/content_first.py
@@ -23,6 +23,8 @@ def render_page_ir(page: PageIR) -> tuple[str, str]:
                 lines.append(f"${body}$")
         elif seg.kind is SegmentKind.MARK_NOTE:
             lines.append(f"(鍒嗚ɑ: {seg.text})")
+        elif seg.kind is SegmentKind.FIGURE:
+            lines.append(f"(鍦? {seg.text})")
         else:
             lines.append(seg.text)
     joined = "\n".join(lines)
@@ -62,6 +64,7 @@ def apply_integrity_to_page(page: PageIR) -> tuple[PageIR, list[str]]:
                     source_block_id=seg.source_block_id,
                     bbox=seg.bbox,
                     integrity=status,
+                    crop_relpath=seg.crop_relpath,
                 )
             )
         else:
@@ -82,6 +85,7 @@ def write_pageir_json(path: Path, pages: list[PageIR]) -> None:
                         "source_block_id": s.source_block_id,
                         "bbox": [s.bbox.x1, s.bbox.y1, s.bbox.x2, s.bbox.y2],
                         "integrity": s.integrity.value,
+                        "crop_relpath": s.crop_relpath,
                     }
                     for s in p.segments
                 ],
diff --git a/src/ocr_pipeline/models.py b/src/ocr_pipeline/models.py
index f93622a..c71febf 100644
--- a/src/ocr_pipeline/models.py
+++ b/src/ocr_pipeline/models.py
@@ -83,6 +83,7 @@ class SegmentKind(str, Enum):
     PROSE = "prose"
     MATH = "math"
     MARK_NOTE = "mark_note"
+    FIGURE = "figure"
 
 
 class IntegrityStatus(str, Enum):
@@ -100,6 +101,7 @@ class ContentSegment:
     source_block_id: str
     bbox: BBox
     integrity: IntegrityStatus = IntegrityStatus.OK
+    crop_relpath: str | None = None
 
 
 @dataclass
diff --git a/tests/test_content_first.py b/tests/test_content_first.py
index 57cd5c6..bbc2f47 100644
--- a/tests/test_content_first.py
+++ b/tests/test_content_first.py
@@ -124,6 +124,47 @@ def test_pipeline_writes_pageir_after_content_first(tmp_path: Path):
     assert warnings
 
 
+def test_render_figure_as_caption_stub():
+    page = PageIR(
+        page_index=1,
+        segments=[
+            ContentSegment(
+                kind=SegmentKind.FIGURE,
+                text="鍦撳舰闈㈢绀烘剰鍦?,
+                source_block_id="p001_b012",
+                bbox=BBox(0, 0, 10, 10),
+                crop_relpath="figures/p001_b012.png",
+            )
+        ],
+    )
+    txt, tex_body = render_page_ir(page)
+    assert txt == "(鍦? 鍦撳舰闈㈢绀烘剰鍦?"
+    assert tex_body == "(鍦? 鍦撳舰闈㈢绀烘剰鍦?"
+
+
+def test_write_pageir_json_includes_crop_relpath(tmp_path: Path):
+    pages = [
+        PageIR(
+            page_index=1,
+            segments=[
+                ContentSegment(
+                    kind=SegmentKind.FIGURE,
+                    text="绀烘剰鍦?,
+                    source_block_id="p001_b012",
+                    bbox=BBox(0, 0, 10, 10),
+                    crop_relpath="figures/p001_b012.png",
+                )
+            ],
+        )
+    ]
+    path = tmp_path / "demo.pageir.json"
+    write_pageir_json(path, pages)
+    data = json.loads(path.read_text(encoding="utf-8"))
+    seg = data["pages"][0]["segments"][0]
+    assert seg["kind"] == "figure"
+    assert seg["crop_relpath"] == "figures/p001_b012.png"
+
+
 def test_finalize_strips_tabular_chrome_from_polished_draft(tmp_path: Path):
     from ocr_pipeline.assemble import FinalPolisher
     from ocr_pipeline.content_first import finalize_content_first
diff --git a/tests/test_page_ir_models.py b/tests/test_page_ir_models.py
index d30af36..63c2cf0 100644
--- a/tests/test_page_ir_models.py
+++ b/tests/test_page_ir_models.py
@@ -55,3 +55,15 @@ def test_page_ir_holds_ordered_segments():
 def test_integrity_status_includes_repaired_and_fail():
     assert IntegrityStatus.REPAIRED.value == "repaired"
     assert IntegrityStatus.FAIL.value == "fail"
+
+
+def test_content_segment_figure_has_crop_relpath():
+    seg = ContentSegment(
+        kind=SegmentKind.FIGURE,
+        text="鍦撳舰闈㈢绀烘剰鍦?,
+        source_block_id="p001_b012",
+        bbox=BBox(1, 2, 3, 4),
+        crop_relpath="figures/p001_b012.png",
+    )
+    assert seg.kind is SegmentKind.FIGURE
+    assert seg.crop_relpath == "figures/p001_b012.png"
```

