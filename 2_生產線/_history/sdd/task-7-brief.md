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
1. uv run python run_ocr_pipeline.py --pdf data/sources/<doc>.pdf --limit 1
2. Confirm output/<stem>/figures/*.png and pageir figure segments
3. uv run python -m ocr_pipeline.batch_export --docs <stem> --publish --ingest --share-root Z:/
4. Qdrant: point kind=figure, crop_path set, chunk_version=pageir_v2
```

- [ ] **Step 4: Commit docs (only if user asked)**

```bash
git add task_plan.md findings.md progress.md handoff.md
git commit -m "docs: figure ingest + batch CLI status"
```

---
