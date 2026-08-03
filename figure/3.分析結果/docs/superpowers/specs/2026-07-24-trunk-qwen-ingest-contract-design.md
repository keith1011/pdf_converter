# Design: Trunk Qwen + ingest contract (text / figure / batch)

**Date:** 2026-07-24  
**Status:** Approved in brainstorming (approaches + §§1–3)  
**Product:** P-ocr feedstock → Qdrant on PC-B  

## Goal

Lock the OCR trunk on **Qwen2.5-VL**, extend the **ingest contract** so each job can carry **text segments plus figure crops with captions**, add **batch publish→ingest** from local `3.分析結果/output/`, keep **GOT / UniMERNet as formula-only knives**, and defer **ColPali** until the question bank is large enough—without blocking current ingest.

## Non-goals (this milestone)

- ColPali / late-interaction visual page retrieval
- DONE.json schema v2 or a second Qdrant collection for figures
- Batch ingest by scanning `Z:\jobs` for “not yet ingested” (may come later)
- Changing the marking-scheme teacher bar or re-ranking engine scorecards

## Locked decisions

| Decision | Choice |
|----------|--------|
| Trunk VLM | **Qwen2.5-VL-7B-Instruct 4bit** (greedy) for text / polish / figure captions |
| Trunk layout | **MinerU** (locked 2026-07-24; replaces Surya as default) |
| Specialty knives | `engines.formula`: got / unimernet **only**; never default text path |
| Figure ingest | Caption text embedded; crop PNG stored on job; path in payload |
| When to extract figures | Any layout `FIGURE` / picture block (both `marking_scheme` and `question_paper`) |
| Batch UX | One CLI: list of doc ids from local `3.分析結果/output/` → sequential stage→publish→ingest |
| DONE schema | Remain **`done_schema: 1`**; figures appear as artifact paths under `figures/` |
| Collection | Keep **`exam_segments_v1`**; bump **`chunk_version` → `pageir_v2`** for new point ids |
| ColPali | Backlog only; does not block recording |

## Architecture

```text
PDF
  → trunk OCR (MinerU layout + Qwen2.5-VL text/polish/formula; optional formula knife)
  → for each FIGURE block: crop PNG + Qwen short caption
  → artifacts: {doc}.txt / .tex / .pageir.json + figures/*.png
  → batch CLI: for each doc_id → stage → publish(Z:/jobs) → ingest
  → Qdrant exam_segments_v1
       prose/math/mark_note: embed body text
       figure: embed caption; payload.crop_path = figures/...
ColPali: later layer only
```

### Ownership

| Layer | Owns |
|-------|------|
| OCR trunk | Always Qwen2.5-VL for text/captions; formula knives optional via config |
| Ingest contract | pageir + DONE artifacts (schema 1); `chunk_version=pageir_v2` |
| Batch | Local `3.分析結果/output/` → Samba jobs → Qdrant writer |
| Homelab ops | B host, keys, ufw, backups (unchanged Wave 1) |

## Data contract

### pageir segment (figure)

```json
{
  "kind": "figure",
  "text": "Qwen-generated short caption (Traditional Chinese)",
  "source_block_id": "p001_b012",
  "bbox": [x1, y1, x2, y2],
  "integrity": "ok",
  "crop_relpath": "figures/p001_b012.png"
}
```

- Non-figure segments: omit `crop_relpath` or set `null`.
- Linear `.txt` / `.tex`: render a one-line caption stub (e.g. `(圖: …)`); do not embed PNGs in TeX.

### DONE.json (`done_schema: 1`)

- Required artifact: `{doc_id}.txt`
- Optional: `{doc_id}.tex`, `{doc_id}.pageir.json`
- Figure crops listed in `artifacts` as relative paths such as `figures/p001_b012.png` with sha256
- Publish/stage copies the `figures/` directory into the job

### Qdrant `exam_segments_v1`

| Field | Content |
|-------|---------|
| vector | nomic-embed of `text` (for figures: the caption) |
| `kind` | `prose` \| `math` \| `mark_note` \| `figure` |
| `crop_path` | figure only: job-relative path; omit otherwise |
| `chunk_version` | **`pageir_v2`** |
| point id | uuid5 over `doc_id\|page\|segment_id\|embedding_model\|chunk_version` |

Re-ingest the same `doc_id` with `--reindex` deletes prior points for that doc before upsert (existing behavior).

## OCR behavior

1. Run layout (**default MinerU**; Surya/DocLayout optional).
2. Route text/table via Qwen (trunk); formulas via configured formula engine (default Qwen; optional got/unimernet).
3. For each figure-like block: write crop under a staging figures dir keyed by stem/block id; call Qwen with a short caption prompt; append a `figure` segment to pageir.
4. Finalize txt/tex/pageir as today, including figure caption lines.
5. Config comments lock trunk: `engines.text=vlm`, `engines.formula` specialty knives documented as formula-only.

`question_paper` mode remains stem-first; if layout still emits figure blocks on a cropped page, they follow the same figure path (per approved “any FIGURE” rule).

## Batch CLI

Suggested entry (final name in implementation plan):

```text
uv run python -m ocr_pipeline.batch_export --docs 123,789 --share-root Z:/ --publish --ingest
# or --from-file docs.txt
```

- Resolves artifacts from `3.分析結果/output/` (stem or `stem.tag` via existing staging rename to `doc_id`).
- Per doc: stage → publish → ingest.
- Default: on failure, log `doc_id` + error and **continue**; optional `--fail-fast`.
- Preflight: share root writable + writer key present before starting the batch.

## Error handling

| Case | Behavior |
|------|----------|
| Caption/crop fails for one figure | Warn; skip that figure segment; keep document artifacts |
| Missing Z: or writer key | Fail before batch starts |
| Single job publish/ingest error | Log and continue (unless `--fail-fast`) |
| pageir lists crop but file missing at publish | Fail that job’s publish with clear hash/path error |

## Testing

- Unit: pageir figure field round-trip; ContentSegment `crop_relpath`
- Publish: staging includes `figures/*.png` in DONE artifacts
- Ingest (mocked Qdrant/embedder): figure payload has `crop_path`; embed input is caption
- Batch: two fake docs; assert call order; one failure does not stop the second

## Rollout / compatibility

- Old jobs (`chunk_version=pageir_v1`) remain readable; new writes use `pageir_v2`.
- No migration job required for this milestone.
- ColPali may later consume `crop_path` / page images without changing the text embed path.

## Success criteria

1. Default config documents and uses Qwen2.5-VL trunk; formula knives are opt-in only.
2. A doc with at least one figure produces pageir figure segments, job `figures/*.png`, and Qdrant points with caption vectors + `crop_path`.
3. Batch CLI can publish+ingest multiple local docs in one command with per-doc error isolation.
4. Spec and planning docs list ColPali as explicit backlog, not a dependency of ingest.
