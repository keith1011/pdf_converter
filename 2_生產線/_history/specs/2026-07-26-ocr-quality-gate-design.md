# Design: OCR → vector quality gate

**Date:** 2026-07-26  
**Status:** Approved  
**Product:** P-ocr feedstock → `exam_segments_v1` (Qdrant on B)

## Goal

Define **measurable** quality gates so we only put retrieval-useful segments into the exam vector store—without blocking Wave‑1 DONE/`pageir_v2` contracts or requiring a second collection.

## Non-goals (this design)

- Fixing MinerU MCQ atomization / coalesce (upstream; gated separately)
- DONE.json schema bump (`done_schema` stays **1**)
- New Qdrant collection or ColPali
- Teacher edit-time scorecard / human gold labels (optional later)

## Evidence (baseline)

`2014-DSE-MATH-CP-2.nup-v2.pageir.json` (2026-07-25):

| Metric | Value | Note |
|--------|------:|------|
| segments | 364 | 8 pages |
| `len ≤ 3` | **27.7%** | was ~45% pre-coalesce hints |
| `len ≥ 20` | **22.5%** | barely usable for RAG |
| `len ≥ 40` | **9.1%** | “stem-like” rare |
| bare option-only | ~1 | coalesce helps letters; paren/CJK still atomized |
| integrity | all `ok` | **not** a quality signal |

**Verdict:** contract-ready ≠ retrieval-ready. Gates must treat PageIR as noisy feedstock.

## Locked decisions

| Topic | Choice |
|-------|--------|
| Where to gate | **Two layers:** (A) segment admit at **ingest**; (B) doc report + pass/fail before **batch publish→ingest** |
| Math floor | **`len ≥ 8`** and latex-ish (`\` / `$` / `=`); else prose floor |
| Hard refuse | Doc **hard-fail** → skip ingest unless `--ingest-partial` or `--force-ingest` |
| Partial path | **`--ingest-partial` allowed** — ingest only admitted segments + write report (canary) |
| Batch default | **`--require-quality-pass` on** for publish→ingest batch |
| DONE schema | **Unchanged** (`done_schema: 1`) |
| Quality artifact | Sidecar **`{doc_id}.quality.json`** (optional in job; listed in DONE artifacts when present) |
| Collection | Keep **`exam_segments_v1`**; keep **`chunk_version=pageir_v2`** |
| Upstream vs gate | Gate **does not replace** MCQ coalesce; coalesce raises scores, gate protects the DB |

## Architecture

```text
OCR finalize
  → quality_report(pageir) → {doc}.quality.json + console summary
  → batch publish→ingest:
       if verdict=fail and not (--ingest-partial|--force-ingest):
         skip ingest (publish OK)
       else:
         ingest Layer A filter → upsert admitted
```

### Ownership

| Layer | Owns |
|-------|------|
| `ocr_pipeline.quality` (new) | Metrics, admit rules, report JSON schema |
| `finalize` / batch CLI | Emit `{doc}.quality.json` next to pageir |
| `homelab/ingest` | Enforce admit filter; honor `--require-quality-pass` / `--ingest-partial` |
| Human | Tune thresholds from golden docs; `--force-ingest` escape |

## Layer A — Segment admit (always on at ingest)

Apply **after** `load_segments`, **before** embed. Dropped segments are logged, not upserted.

### Always drop

| Rule | Regex / condition |
|------|-------------------|
| Empty | `not text.strip()` |
| Bare option letter | `^[A-Da-d][.．]?\s*$` |
| Punct / paren only | `^[。．.、，,()（）\s]+$` |
| Single CJK digit/numeral (no context) | `^[\u4e00-\u9fff]$` **or** `^\d{1,2}[.．]?\s*$` (Q-number alone) |

### Kind-aware minimum length

| `kind` | Admit if |
|--------|----------|
| `prose` | `len ≥ 12` |
| `math` | `len ≥ 8` **and** looks like math (`\` or `$` or `=`)；else treat as prose (`≥ 12`) |
| `figure` | `len ≥ 4` (caption) **and** `crop_path` present when kind=figure |
| `mark_note` | `len ≥ 8` |

Rationale: keep real formulas (`\frac{1}{32n^{15}}` is len≥8); kill `(` / `一` / lone `A.` / tiny latex shreds.

### Payload (unchanged fields)

No new required payload keys for MVP. Optional later: `quality_admit: true` (omit to avoid payload bloat).

## Layer B — Doc quality report

Computed on full PageIR (before filter), written to `{doc_id}.quality.json`.

### Metrics

```json
{
  "quality_schema": 1,
  "doc_id": "2014-DSE-MATH-CP-2",
  "n_segments": 364,
  "pct_le3": 0.277,
  "pct_ge20": 0.225,
  "pct_ge40": 0.091,
  "bare_option_only": 1,
  "punct_or_paren_only": 8,
  "single_cjk_only": 22,
  "n_figure": 17,
  "n_with_version_id": 347,
  "pct_admitted_est": 0.31,
  "verdict": "fail",
  "fail_reasons": ["pct_le3>0.20", "pct_ge20<0.35"]
}
```

`pct_admitted_est` = fraction that would pass Layer A (run admit dry-run).

### Thresholds (v1 defaults)

| Metric | Soft warn | Hard fail |
|--------|-----------|-----------|
| `pct_le3` | > 0.15 | **> 0.20** |
| `pct_ge20` | < 0.40 | **< 0.35** |
| `bare_option_only` | > 5 | **> 15** |
| `pct_admitted_est` | < 0.40 | **< 0.25** |
| `n_segments` | — | **< 1** |

**Verdict**

- `pass` — no hard fail (soft warns OK)
- `warn` — soft only
- `fail` — any hard fail

`nup-v2` today: **fail** (`pct_le3=0.277`, `pct_ge20=0.225`) — correct; use `--ingest-partial` for canary only.

### Version balance (nup docs only; soft)

If ≥20% of segments have `version_id` and both `v0`/`v1` appear:

| Metric | Soft warn |
|--------|-----------|
| `min(n_v0,n_v1) / max(n_v0,n_v1)` | < 0.35 |

Does **not** hard-fail MVP (classifier imbalance ≠ junk text).

## CLI / batch behavior

| Flag | Effect |
|------|--------|
| (default) | Emit quality.json on finalize; ingest always applies Layer A |
| `--require-quality-pass` | **Batch default ON** — skip ingest when verdict=`fail` |
| `--ingest-partial` | Override: ingest admitted segments even if doc `fail`/`warn` |
| `--force-ingest` | Bypass doc gate (still apply Layer A unless `--no-admit-filter`) |
| `--no-admit-filter` | Escape hatch for debugging only |

Manual `ingest.py --job-dir …`: Layer A **on**; if `{doc}.quality.json` present and verdict=`fail`, refuse unless `--ingest-partial` or `--force-ingest`.

## Testing plan

1. Unit: admit rules (bare `A.`, `(`, `一`, math len 7 drop / len≥8 keep, long prose).
2. Unit: report thresholds → `pass`/`warn`/`fail` on synthetic pageir.
3. Fixture: slice of `nup-v2` pageir → expect `fail` + `pct_admitted_est` in band.
4. Ingest dry-run (no Qdrant): print `WOULD_UPSERT` / `WOULD_DROP` counts.
5. Batch: fail doc without flags → no ingest; with `--ingest-partial` → admitted only.

## Rollout

1. Land `quality` module + tests + finalize emit.
2. Wire Layer A into ingest; wire doc gate with batch `--require-quality-pass` default **on**.
3. Canary: `nup-v2` via `--ingest-partial` only; do not full-ingest failing goldens.
4. Re-tune thresholds after MCQ coalesce improves `pct_ge20`; record in `findings.md`.

## Success criteria

- Failing docs cannot silently fill `exam_segments_v1` (require-pass default).
- `--ingest-partial` canary upserts only Layer‑A survivors.
- Admitted set excludes bare options / paren / single-CJK / math `<8`.
- Quality JSON is reproducible from pageir alone (no GPU).
- DONE / `pageir_v2` point ids unchanged for surviving segments.
