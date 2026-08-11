### Task 5: Ingest `pageir_v2` + `crop_path` payload

**Files:**
- Modify: `homelab/ingest/ingest.py`
- Test: `tests/test_ingest_figures.py`

**Interfaces:**
- Consumes: pageir segments with `kind=figure` and `crop_relpath`
- Produces: `CHUNK_VERSION = "pageir_v2"`; `load_segments` includes `crop_path` (from `crop_relpath`); payload omits `crop_path` for non-figures

- [ ] **Step 1: Write failing test**

```python
# tests/test_ingest_figures.py
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

Run: `uv run pytest tests/test_ingest_figures.py -q`

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

Run: `uv run pytest tests/test_ingest_figures.py -q`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add homelab/ingest/ingest.py tests/test_ingest_figures.py
git commit -m "feat: ingest figure captions as pageir_v2 with crop_path"
```

---
