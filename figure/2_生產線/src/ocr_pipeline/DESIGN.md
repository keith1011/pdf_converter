# OCR pipeline design

## Active path

```text
PDF
  → page PNGs
  → layout blocks
  → Stage2 crop OCR
  → draft assembly
  → Stage3 polish or deterministic MCQ sanitize
  → PageIR / TXT / TEX / questions.jsonl / quality report
```

`factory.py` builds the configured engines and `PipelineManager` coordinates
the run. The default trunk is MinerU layout plus local Qwen3-VL text and formula
OCR. Optional GOT, UniMERNet, PP-OCR, DocLayout-YOLO, and Surya adapters remain
available through `engines.*`.

## DSE Paper 2 MCQ

The DSE-specific regioner produces one layout block per question, including the
stem, figure, and choices A–D. Stage1 owns `meta.question_id`; Stage2 must not
redetect it.

For MCQ, Stage3 defaults to `sanitize`. The pipeline coalesces each question
into exactly one PageIR segment and checks Q1–Q45 coverage before formal ingest.

The optional Instructor backend runs in shadow mode through an
OpenAI-compatible endpoint. It does not replace or patch the local 4-bit
Transformers backend.

## Output safety

- Keep `nup.enabled: false` for the locked DSE path.
- Keep one GPU pipeline process at a time.
- Preserve teacher-reviewable drafts; never ingest failed quality output.
- `sanitize_tex_document` remains the final deterministic TeX safety pass.
