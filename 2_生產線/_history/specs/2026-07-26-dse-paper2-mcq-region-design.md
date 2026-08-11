# Design: DSE Paper2 MCQ question-region (1題1框)

**Date:** 2026-07-26
**Status:** Approved (grill confirmed)
**Product:** P-ocr — DSE MATH CP Paper 2 MCQ path (B layout → A VLM)

## Goal

Cut **one layout box per MCQ** (stem + optional figure + options A–D) so Stage2/3 VLM sees a whole question per call—eliminating MinerU/PP-DocLayout over-fragmentation that drives high `pct_le3` and quality-gate fail.

## Non-goals (v1)

- Swapping general DocLayout packages as the primary fix
- Dual-version / N-up auto-split (`nup.enabled` stays false; user flattens)
- Dual-column within page (profile switch exists, **default off**)
- Paper 1 / marking schemes / non-MATH subjects as v1 gold
- Quality-gate pass / formal ingest as v1 success criteria (next stage)
- Replacing Qwen VLM trunk or DONE/`pageir_v2` contracts
- Training a question-detector CNN (rules + light OCR first)

## Evidence (why)

- Current MinerU path atomizes formulas / options into many tiny blocks → many VLM calls → short segments.
- Existing coalesce (`assemble.coalesce_stitched_fragments`, `segmenter.coalesce_mcq_segments`) insufficient when layout already shredded.
- Ideal locked: **1 MCQ = 1 box**; option/symbol shreds = fail.
- Math stems contain digits and in-stem `1.` → boundary cannot be number-only.

## Locked decisions

| Topic | Choice |
|-------|--------|
| Ideal | **1 question = 1 box** (stem + figure + A–D) |
| Approach | **DSE Paper2 specialized region rules** (not generic layout bakeoff) |
| Pipeline hook | **Image / light line OCR → question ROI → VLM** (bypass MinerU shreds on this path) |
| Boundary signals | **Question number opens**; **A–D option anchors** confirm/close |
| Subject v1 | **MATH CP Paper 2** only; implement as **extensible subject profiles** |
| Dual-column | Profile flag, **default off**; v1 assumes single column |
| Compute split | **B** = light OCR + region cut → `layout.json`; **A** = VLM via `--reuse-layout` |
| Figures | **Inside the same question ROI** (still one VLM call) |
| v1 success | **Box correctness** (count ≈ truth; most boxes contain stem+A–D); quality gate later |

## Architecture

```text
PDF → page PNG (existing rasterize; single-column, user-flattened)
  → [B] light OCR / line detect (PP-OCR or equivalent)
  → [B] dse_mcq_region (MATH CP profile):
         find stem openers (Q-number patterns at line start / left margin)
         find A–D anchors; pair opener → closed MCQ span
         emit one bbox per question (union stem..D, include figures in span)
  → write crops + layout.json (source=dse_mcq_region)
  → [A] run_ocr_pipeline --reuse-layout
         one LayoutBlock ≈ one MCQ → TextRouter / polish as today
  → finalize → optional quality.json (not v1 pass requirement)
```

```mermaid
flowchart LR
  png[page PNG] --> ocrB[B light OCR lines]
  ocrB --> rules[題號 open + A-D close]
  rules --> roi[1 ROI per MCQ]
  roi --> lay[layout.json]
  lay --> vlm[A VLM per block]
  vlm --> arts[".txt / .tex / .pageir"]
```

### Ownership

| Layer | Owns |
|-------|------|
| `dse_mcq_region` (new; run on B) | Profile config, line grouping, Q-number + A–D pairing, bbox union, crops |
| Subject profile YAML | Patterns (stem opener, option letters), margins, dual-column flag |
| `layout_artifact` | Existing `layout.json` v1 contract — **reuse**; set `source` + per-block `meta` |
| A-side pipeline | Unchanged Stage2/3 given question-sized `TEXT` blocks |
| Quality gate | Unchanged; evaluate after boxes are good |

### Fallback

| Condition | Behavior |
|-----------|----------|
| No A–D found after opener | Soft-fail: extend to next opener or page bottom; flag `meta.mcq_incomplete=true` |
| Region detector crash / empty | Fall back to **existing MinerU layout** for that page (log WARN); do not invent boxes |
| Dual-column page with flag off | Treat as single column (may mis-merge); document as known limit |

## Data contract

### Reuse `layout.json` (version 1)

Compatible with `layout_artifact.py`. One block per MCQ:

```json
{
  "version": 1,
  "source": "dse_mcq_region:math_cp_p2",
  "pdf": "...",
  "pages": [
    {
      "page": 1,
      "image_path": ".../page_001.png",
      "blocks": [
        {
          "block_id": "p001_q003",
          "block_type": "text",
          "bbox": [x1, y1, x2, y2],
          "order": 3,
          "page": 1,
          "image_path": ".../page_001.png",
          "crop_path": ".../crops/p001_q003.png",
          "raw_text": "",
          "latex": "",
          "meta": {
            "question_id": 3,
            "profile": "math_cp_p2",
            "anchors": {"A": true, "B": true, "C": true, "D": true},
            "mcq_incomplete": false
          }
        }
      ]
    }
  ]
}
```

- `block_type`: **`text`** (VLM text/math mix in one crop; no separate formula blocks in v1).
- Optional sidecar for debug: `mcq_regions.json` (lines, scores) — not required for `--reuse-layout`.

### Profile sketch (`config/profiles/math_cp_p2.yaml`)

```yaml
id: math_cp_p2
dual_column: false
stem_opener:
  # line-start / left-gutter biased; not bare mid-line "1."
  patterns: ["^\\s*(\\d{1,2})[.．]\\s+", "^\\s*\\((\\d{1,2})\\)\\s+"]
option_anchors:
  letters: ["A", "B", "C", "D"]
  patterns: ["^[A-D][.．、)]\\s+", "^\\([A-D]\\)\\s+"]
margins:
  left_bias_ratio: 0.25   # openers/options prefer left portion of column
min_option_hits: 3        # require ≥3 of A–D to close; else incomplete
```

## Boundary algorithm (v1)

1. Run light OCR → ordered **lines** with bboxes (reading order top→bottom).
2. Tag lines: `stem_candidate` if opener pattern **and** x-position in left bias; `option_X` if option pattern + left bias.
3. Walk top→bottom: on `stem_candidate` with new `question_id`, start region; collect until next stem **or** after seeing enough A–D (prefer close after **D**).
4. Reject false openers: mid-column / indented `1.` without following option structure nearby.
5. BBox = union of member line boxes (+ small pad); include any ink/figure contours fully inside y-span and column x-span.
6. Write crop PNG + layout block.

## Success metrics (v1)

| Metric | Pass bar (MATH CP P2 gold pages) |
|--------|----------------------------------|
| Questions detected / page | Within ±1 of human count (spot-check) |
| Boxes with A–D present | ≥80% of detected questions (visual / meta.anchors) |
| Blocks per page | ≈ question count (not dozens of formula shreds) |
| Quality `pct_le3` / admit | **Not** v1 gate; measure as Stage-2 KPI after VLM |

Gold set (existing sources): `2012p2` … `2016p2` / `2014-DSE-MATH-CP-2` — use **flattened single-page** inputs only.

## Testing strategy

- Unit: opener/option regex + pairing on synthetic line lists (false `1.` in stem must not open).
- Fixture: 1–2 real page PNGs + expected question count / rough bboxes.
- Integration: B script writes `layout.json` → A `--reuse-layout` limit-1 smoke (optional in CI without GPU).

## Risks

| Risk | Mitigation |
|------|------------|
| Light OCR misreads `A.`/`D.` | Require ≥3 option hits; incomplete flag; pad bbox generously |
| Figure between Qn and Qn+1 | y-span union until next opener; left-bias column clip |
| Header/footer / 甲部 titles | Skip non-numeric section lines; top/bottom margin crop optional |
| B PP-OCR deps on Windows vs Ubuntu | Prefer run region stage on B Ubuntu; ship script + profile in repo |

## Open for implementation plan (not blocking design)

- Exact PP-OCR vs Paddle line API on B
- Whether Stage2 prompt gets a `mcq_question` variant (whole-question transcribe) — default: reuse TEXT router first
- CLI flag `--layout-engine dse_mcq` vs separate `scripts/dse_mcq_regions.py` then reuse-layout

## Next

1. Writing-plans → TDD tasks (region module + profile + layout writer)
2. Implement B-side cutter; smoke one MATH CP P2 page
3. Re-measure quality after A-side VLM (Stage-2 KPI)
