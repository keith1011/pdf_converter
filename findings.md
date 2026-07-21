# Findings & Decisions

## Goal (refresh)
PDF → compile-friendly `.tex` draft → ≤10 min teacher edit → xelatex. Competitor = hand-typed LaTeX.

## Phase 2.5a delivery order (locked)
1. **T1 TexSanitize** — teacher can compile
2. **T7 VlmClient + Qwen 4bit** — stop VRAM thrash
3. T2–T6, then golden
4. Later: LayoutArtifact → MinerU

## T1 — what breaks today (2026-07-21)
| Bug | Where | Effect |
|-----|-------|--------|
| Global `$$…$$` with DOTALL | `latex_math.normalize_math_in_tex` L165–178 | Matches across tabular cells → uncompilable |
| Conflicting prompts | `prompts.py` / DESIGN | “一律 $$” vs table needs `$` |
| Double preamble | `pipeline.py` polish_per_page | Nested `\documentclass` |
| `arrange_only --no-vlm` | same `normalize_math_in_tex` | Must use new sanitizer |

## T1 target API (from eng plan)
- `sanitize_tex_document(tex) -> str`
- Split `tabular` vs body; inside tabular: `$$` → `$`, `<br>` → `\\`
- Outside: display math OK; unpaired `$` → `% TODO: verify` fail-open
- Call from `assemble.py` + `arrange_only.py` instead of/after normalize

## CLI DX (DR1–DR9) — implement in T5, not now
- Short success: TEX / Next / optional one-line WARN
- Stage3 quiet after one line; preflight once at start
- exit 0 if `.tex` written; plain text no ANSI
- `arrange_only` same success block

## TODOS vs now
| Item | When |
|------|------|
| VlmClient + Qwen P1 | T7 after/parallel T1 |
| check-compile / Approach B / LayoutArtifact | P2 after golden |
| MinerU | P3 after golden + evidence |

## Golden success (2026-07-21)
- Pipeline OK after VRAM release ordering
- Auto-extract TeX from markdown fences
- ~1 min human edit (unbalanced `{` in marks remarks) → `output/123.pdf`
- Phase 2.5a acceptance met for 1-page golden
| Task | Status | Note |
|------|--------|------|
| T1–T4, T7 | done | 12+ unit tests; Qwen GPU smoke still pending |
| T5 CLI DX | done | `cli_report.py`; DR1–DR9 |
| T6 README | done | teacher loop + Stage3 silence |
| Golden | next | user asked: finish code first, then run |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| No module named pytest | 1 | pip install pytest in .venv |
| PowerShell `$$` in -c | 1 | Use pytest file instead |
| `≤` shows as `→` on console | 1 | ASCII `<=10m` in CLI |

## Resources
- Eng plan: `~/.gstack/projects/pdf-scaner/a1217-main-eng-review-plan-20260721.md`
- Design: `~/.gstack/projects/pdf-scaner/a1217-main-design-20260721-101300.md`
- Arch HTML: `%TEMP%/architecture-review-20260721-pdf-scaner.html`
