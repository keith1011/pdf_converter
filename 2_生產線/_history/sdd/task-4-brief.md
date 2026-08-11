### Task 4: Job staging + publish copies `figures/`

**Files:**
- Create: `src/ocr_pipeline/job_stage.py`
- Modify: `homelab/ingest/publish.py`
- Modify: `homelab/ingest/done.py` (optional disk check for figures/)
- Test: `tests/test_job_stage.py`
- Test: `tests/test_done_schema.py`

**Interfaces:**
- Produces:
  - `def stage_job_dir(*, doc_id: str, output_dir: Path, staging_dir: Path) -> Path`
    - Copies `{doc_id}.txt` (required), `.tex`/`.pageir.json` if present
    - Copies `output_dir/{doc_id}/figures/*.png` → `staging_dir/figures/*.png`
  - `publish(..., source_dir=staging_dir)` already copies every file listed in artifacts — extend publish to discover `figures/**` under `source_dir` and add to `artifacts_src`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_job_stage.py
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

Extend `tests/test_done_schema.py`:

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

Run: `uv run pytest tests/test_job_stage.py tests/test_done_schema.py::test_validate_done_with_figures_artifact -q`

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

Run: `uv run pytest tests/test_job_stage.py tests/test_done_schema.py -q`

Expected: PASS

Also smoke (no Z: required):

```python
# optional local unit using tmp share root
```

Add `tests/test_publish_figures.py` if needed:

```python
def test_publish_includes_figures(tmp_path: Path):
    import sys
    sys.path.insert(0, str(Path("homelab/ingest").resolve()))
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
git add src/ocr_pipeline/job_stage.py homelab/ingest/publish.py homelab/ingest/done.py tests/test_job_stage.py tests/test_done_schema.py tests/test_publish_figures.py
git commit -m "feat: stage and publish figure artifacts"
```

---
