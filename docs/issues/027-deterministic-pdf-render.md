# [Refactor]: Deterministic PDF render from structured tailored data

## Description

The PDF generator previously received free-form text blobs (`sections: dict[str, str]`) and paragraph-split them on `\n\n`. Rewritten to render from the structured `ResumeMaster + TailoredResume`, so the visual layout is controlled by our code — not by LLM-produced whitespace.

## Motivation

LLM-produced blobs meant layout was at the mercy of LLM output formatting. A stray double-newline shifted spacing. Bullets became paragraphs. We couldn't tune margins, fonts, or bullet styles without re-prompting.

Structured render means the PDF is a pure function of the tailored data — predictable, reviewable, no LLM involvement in rendering.

## Implementation

- [x] [`tools/pdf_generator.py`](../../src/resume_operator/tools/pdf_generator.py) rewritten — new signature `generate_pdf(master, tailored, output_path, template, facts=None)`. Returns `Path`.
- [x] Internal `_RenderPlan` groups kept/reworded `TailoredItem`s by kind (summary, experience-bullet, project, education, skill, certification).
- [x] Experience renders as proper role headers (from `master`) with bullets underneath; `extra-bullet[role-id]` items from the facts bank splice into the correct role.
- [x] Skills render as a flow with `•` separators (not a single line dump); `Projects` get their own subsection.
- [x] Paragraph-splitting-on-newline logic removed entirely. No `\n\n` heuristics.
- [x] [`nodes/generate_pdf.py`](../../src/resume_operator/nodes/generate_pdf.py) passes `state.master`, `state.tailored_resume`, `state.facts`, and the configured template.
- [x] Template selection via `RESUME_TEMPLATE` env var (`default | compact | modern`); unknown values fall back to default with a warning. Stub for future templates.
- [x] [`config.py`](../../src/resume_operator/config.py) and [`.env.example`](../../.env.example) document the new env var.
- [x] PDF generator and node tests rewritten — verify section count, role count, bullet count, dropped items aren't rendered, and reworded bullets show `new_text` not `original_text`.
- [x] `docs/architecture.md` updated.

## Acceptance Criteria — Verified

- `pdf_generator` receives no free-form text blobs ✓ (function signature is now `(master, tailored, output_path, template, facts=None)`; no `dict[str, str] sections` parameter)
- Rendered PDF has consistent spacing regardless of LLM output quirks ✓ (no `\n\n` splits anywhere)
- Dates, roles, and companies appear in structured positions, not as inline paragraph text ✓ (role header from master.role/company, dates in role_meta_style, etc.)

## Proof of Work

Real-run rendering against OpenRouter + `openai/gpt-4o-mini`:

```
optimize_content: completed — items=27 (kept=25, reworded=0, dropped=2), fabricated_rejected=1, notes=1
pdf_generator: completed — roles=3, bullets=8, skills=12, data/test_027.pdf
```

Extracted PDF text (selected):
```
Jane Smith
jane.smith@example.com | +1 555 123 4567 | San Francisco, CA
SUMMARY
Senior fullstack engineer with 8 years…
EXPERIENCE
Senior Software Engineer — Acme Corp
Remote | 2021-03 – present
• Led migration of monolith to Go microservices…
• Drove adoption of GitHub Actions across the org…   ← spliced from facts:extra-1
Software Engineer — Widget Labs
San Francisco, CA | 2018-06 – 2021-02
• Shipped React dashboard…
PROJECTS
• Led migration of 20+ Lambda functions from Node.js 14 → 18…   ← from facts:proj-2
SKILLS
Go • TypeScript • React • PostgreSQL • Kubernetes • gRPC • Playwright • Docker • AWS Lambda…
EDUCATION
B.S. Computer Science — State University
CERTIFICATIONS
• AWS Certified Solutions Architect (Associate)
```

Roles, dates, and locations appear in structured positions. Bullets are real bullet items (not paragraphs). The `facts:extra-1` item correctly splices under its target role `exp-1`. The fabrication guard caught one invalid `source_id` (`facts:project-1`, the LLM mistyped) and the rest of the run continued cleanly.

## Key Files

- `src/resume_operator/tools/pdf_generator.py`
- `src/resume_operator/nodes/generate_pdf.py`
- `src/resume_operator/config.py` (`resume_template` setting)
- `.env.example` (`RESUME_TEMPLATE`)
- `tests/test_pdf_generator.py`, `tests/test_generate_pdf.py`
- `docs/architecture.md`

## Dependencies

- #026 ✓ (TailoredResume + SourceIndex)

## Labels

`refactor`, `priority:medium`
