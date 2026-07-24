# P-ocr OCR Branch Comparison Scorecard

## A) Question paper `789.pdf` (full = 1 page) — content crop ON — 2026-07-24

Golden expectation (stems only):

```text
甲部(1)(35分)
1.化簡$\frac{(x^{8}y^{7})^{2}}{x^{5}y^{-6}}$，並以正指數表示答案。（3分）
2.令x成為公式$Ax=(4x+B)C$的主項。(3分)
```

| Branch | Formula edits | Prose edit min | Compile | Notes | layout_s | text/route_s | formula_s | total_s |
|--------|---------------|----------------|---------|-------|----------|--------------|-----------|---------|
| qwen-vl | **0** | **1** | **pass** | `question_paper` + content crop + VLM stem prompt. Matches golden (minor spaces). Artifacts: `output/789.qwen-vl.*` | 0.134 | extract=23.276 | (in extract) | **23.460** |
| got-ppocr | **5** | **8** | **pass** | content crop + DocLayout + PP-OCR + GOT; formula blocks mostly typed as OTHER/plain (`(x{8y7)2`). No stem prompt. `output/789.got-ppocr.*` | 6.012 | route=19.350 | (in route) | **25.365** |
| mineru-ppocr | **3** | **6** | **pass** | content crop + MinerU + PP-OCR + UniMERNet; one good `\\frac{(x^8 y^7)^2}{...}` but prose still shattered. `output/789.mineru-ppocr.*` | 14.853 | route=10.698 | (in route) | **25.555** |

**Ranking (scored columns only; timings log-only):** qwen-vl ≫ mineru-ppocr > got-ppocr.

**Configs:** `config/branches/{qwen-vl,got-ppocr,mineru-ppocr}.yaml` — all set `apply_content_crop: true`.

**Logs:** `output/smoke_789_qwen-vl.log`, `smoke_789_got-ppocr.log`, `smoke_789_mineru-ppocr.log`.

### Layout-only bakeoff (same `page_001.content.png`)

| Engine | layout_s | blocks | Formula typing |
|--------|----------|--------|----------------|
| mineru | **5.059** | 4 | **equation** ✓ |
| doclayout_yolo | **5.126** | 6 | formula_caption → **other** |
| surya v2 | **220.915** (Docker cold) | 5 | no equation; Form/other |

→ **Fastest:** MinerU ≈ DocLayout. **Most precise for math boxes:** MinerU. Surya speed N/A until warm/reuse.

---

## B) Marking scheme `123.pdf` (prior session)

| Branch | Formula edits (score) | Prose edit min (score) | Compile (score) | Notes | layout_s (log) | text_s (log) | formula_s (log) | total_s (log) |
|--------|----------------------|------------------------|-----------------|-------|----------------|--------------|-----------------|---------------|
| qwen-vl | **12** | **7** | **pass** | Full 14p `output/123.tex` (content-first + polish). | — | — | — | — |
| got-ppocr | **22** | **12** | **fail** | **limit-1 + skip_polish** only. | 3.881 | (in route) | (in route) | 33.880 |
| mineru-ppocr | **14** | **10** | **fail** | **limit-1 + skip_polish** only. | 3.380 | (in route) | (in route) | 39.228 |

## Scoring rules

- **Formula edits:** count manual formula-body corrections needed for the golden draft.
- **Prose edit min:** record the teacher's manual editing time in minutes.
- **Compile:** record whether the draft passes `--check-compile` (`pass` / `fail`).
- **Timing columns:** capture wall-clock stage timings from the run log only. They are **not ranking weights**.

## References

- Spec: `docs/superpowers/specs/2026-07-23-ocr-engine-adapters-design.md`
- Plan: `docs/superpowers/plans/2026-07-23-ocr-engine-adapters.md`
- Question-paper mode: `--doc-type question_paper` / `apply_content_crop`
