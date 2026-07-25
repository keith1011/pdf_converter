# Design: N-up classifier + fixed geometric crop (pre-MinerU)

**Date:** 2026-07-25  
**Status:** Approved (brainstorming)  
**Product:** P-ocr feedstock — dual/multi-version exam pages (e.g. 2014 DSE Math CP Paper 2)

## Goal

Stop left/right (and 2×2) **version interleaving** on N-up question papers by detecting N-up layout **before** MinerU, cropping each version panel to its own PNG, then running the existing **MinerU → reading-order → Qwen** trunk per panel.

## Non-goals (MVP)

- XY-Cut++ / adaptive gutter search as the primary splitter
- 8-up (or denser) layouts
- Perfect deskew / non-centered gutter correction
- Mandatory semantic version labels (English/Chinese, A/B) — best-effort only
- Replacing MinerU or changing the Qwen trunk
- Changing DONE.json schema or Qdrant ingest contract

## Locked decisions

| Decision | Choice |
|----------|--------|
| N-up scope | **2-up (L/R)** + **4-up (2×2)**; 8-up deferred |
| Detection | **Classifier** → class ∈ `{1, 2_lr, 4_2x2, uncertain}` + confidence |
| Crop | **Fixed geometry**: midline `x=W/2` for 2-up; quadrant grid for 4-up; optional small margin |
| Uncertain / low conf | **Fall back** to whole-page MinerU (current path) |
| Version IDs | Prefer semantic (EN/ZH, Ver A/B) when cheap rules/heuristics work; else `v0`…`v3` |
| Enablement | **Auto-detect** smart mode (split when confident 2/4; else single) |
| Pipeline shape | Pre-crop gate → per-panel MinerU → existing Stage2/3 |

## Architecture

```text
page PNG
  → NupClassifier(class, confidence)
  → if 1 or uncertain or conf < threshold:
        whole-page MinerU → reading-order → Qwen   (unchanged)
  → if 2_lr:
        FixedCrop midline → panel_L.png, panel_R.png
  → if 4_2x2:
        FixedCrop 2×2 → panel_v0..v3.png
  → for each panel:
        MinerU → assign_reading_order → Qwen route/polish
  → merge panels into page-level PageIR / artifacts
        (each segment carries version_id; page_index unchanged)
  → optional: semantic labeler (rules) maps vN → en|zh|…
```

### Ownership

| Layer | Owns |
|-------|------|
| `nup_classifier` | Class + confidence only (no crop boxes) |
| `nup_crop` | Fixed midline / 2×2 crop + margin; writes panel PNGs |
| `nup_router` | Gate: call classifier, decide fall back vs split, assign `version_id` |
| MinerU + reading-order + Qwen | Unchanged per panel image |
| Semantic labeler (optional MVP) | Best-effort rename of `version_id`; never blocks OCR |

## Data contract

### Panel artifact layout (under page dir)

```text
pages/p001/
  page.png                 # original
  nup.json                 # class, conf, crop boxes, version_ids
  panels/
    v0.png                 # or en.png / zh.png if labeled
    v1.png
    …
  layout.json              # existing; may be per-panel or merged — see plan
```

### `nup.json` (illustrative)

```json
{
  "page_index": 0,
  "class": "2_lr",
  "confidence": 0.91,
  "threshold": 0.75,
  "fallback": false,
  "panels": [
    {"version_id": "v0", "bbox": [0, 0, 0.5, 1.0], "semantic": null},
    {"version_id": "v1", "bbox": [0.5, 0, 1.0, 1.0], "semantic": null}
  ]
}
```

BBoxes are normalized `[x1,y1,x2,y2]` in page coordinates unless noted otherwise in the plan.

### PageIR / segments

- Each segment (or page sub-result) must be attributable to a `version_id`.
- Linear `.txt` / `.tex` order: all of `v0` then `v1` (…), not interleaved across versions.
- `page_index` stays the physical PDF page; do not invent extra page indices for panels.

## Error handling

| Case | Behavior |
|------|----------|
| Classifier conf &lt; threshold | Whole-page path; record `fallback: true` in `nup.json` |
| Classifier error / missing weights | Fail loud **or** fall back whole-page — plan picks one; prefer fall back + warn for MVP resilience |
| Crop writes fail | Fail that page with clear path error |
| Semantic label fails | Keep `vN`; continue |
| Single-column page misclassified as 2-up | Accept as known brittleness; tune threshold / golden; do not add XY-Cut++ in MVP |

## Testing

- Unit: fixed crop boxes for synthetic W×H (2-up and 4-up); margin behavior
- Unit: router — high-conf 2_lr splits; low-conf / `uncertain` / `1` does not
- Unit: merge order — L then R (or v0…v3) with no cross-version interleave
- Fixture: 2014-style dual page (or synthetic L/R with distinct Q numbers) — reading order does not zigzag Q16↔Q19 style
- Regression: single-column page still matches current MinerU path when class=`1` or fallback

## Success criteria

1. On 2014 DSE Math CP-2 (or equivalent dual fixture), pages that are confidently 2-up no longer L↔R interleave question stems after OCR.
2. True single-version pages behave like today’s trunk when classified as `1` or uncertain (fallback).
3. 4-up path crops four panels and processes them independently when confidently detected.
4. Spec remains compatible with existing ingest (`done_schema: 1`); no schema bump required for MVP.
5. Brittle cases (skew, off-center gutter) documented; deferred to post-MVP (micro-adjust or XY-Cut++).

## Rollout

- Default: auto-detect on (config flag to force off / force single for debugging).
- Ship behind clear logging: per-page `nup class=… conf=… fallback=…`.
- Do not block figure crop/caption or batch ingest workstreams.

## Open points for implementation plan (not design blockers)

- Classifier implementation: pure CV heuristics vs tiny trained head vs reuse of an existing light model — choose in plan with 12GB VRAM constraint (prefer CPU/heuristic first).
- Whether `layout.json` is one merged file or `panels/vN/layout.json`.
- Exact confidence threshold default and how it is tuned on golden pages.
