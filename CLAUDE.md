# pdf scaner

Local PDF OCR pipeline: content-first TeX drafts for teacher reuse (Surya layout + VLM polish on RTX 4070 Super).

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- **Writing plan / 實作計畫 / multi-step feature from idea** → Superpowers **`/brainstorming` first** (spec → then `/writing-plans`). Do not jump to writing-plans unless user says spec is already locked.
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- Author a backlog-ready spec/issue → invoke /spec
