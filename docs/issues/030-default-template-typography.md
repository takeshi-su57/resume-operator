# [Feature]: Upgrade the `default` PDF template for recruiter-grade typography

## Description

The `default` template shipped in #027 was a working-but-plain baseline — Helvetica, basic `ParagraphStyle` presets, no visual hierarchy beyond bold section headers. Tighten it so recruiters' eyes land on the parts they care about (name, company, dates, bullet density) while the structural guarantees for ATS parsers stay intact (one column, selectable text, standard fonts, no images).

## Motivation

ATS parsers and recruiters are two audiences with different needs. The structural work in #024–#029 solved the ATS side (structured data → deterministic render). What's left is the recruiter side: a six-second visual scan where the eye follows a name banner, section rules, and right-aligned dates. Moving to a richer engine (WeasyPrint / LaTeX) would be overkill for a single-user local CLI — ReportLab can cover the recruiter-facing gap with template tuning, no new deps, and the output stays pure-text-selectable so ATS extraction is unaffected.

## Target State

After this change, `default` renders:

1. **Name banner** — 22pt Helvetica-Bold name at the top with a 1.2pt deep-blue accent rule immediately underneath.
2. **Contact line** — single greyed row with `·` separators (email · phone · location).
3. **Section headers** — uppercase (`EXPERIENCE`, `SKILLS`, …), 10.5pt bold in the accent colour, with a 0.5pt pale-grey rule spanning the column immediately beneath. This is the primary visual landmark.
4. **Role rows** — a two-column `Table` per role: `Senior Software Engineer — Acme Corp` on the left, `Remote · 2021-03 – present` right-aligned on the same line. Dates at the right margin is the convention recruiters' eyes track.
5. **Bullets** — hanging indent via `leftIndent=14, firstLineIndent=-14` with the `•` glyph inline so a PDF text extractor reads the glyph and its content on the same line (important for ATS parsers that consume text line-by-line). Tighter leading (13pt on 10pt body).
6. **Single accent color** — one muted deep blue (`#2C5282`) used only for the name rule, section labels, and section rules. Body text stays near-black (`#2D3748`).
7. **Tighter margins** — 0.6in side margins instead of 0.75in so a one-pager fits comfortably.

Non-goals for this issue: skills-by-category grouping (would need a schema change on `ResumeMaster.skills`), font embedding, or multi-template A/B. Those can be follow-ups.

### Implementation notes

- Accent rule below name uses `HRFlowable`; pale rule below section headers uses a narrower `HRFlowable` sized to the document frame.
- Role rows use a `Table` with two cells (`alignment=2` on the right cell) — Table is used for *alignment*, not layout content, so the PDF text stream remains single-column from an extractor's POV.
- Bullet glyph is prepended inline (`• <text>`) rather than using `ParagraphStyle.bulletText`, because the latter renders the glyph in a separate region that some PDF text extractors emit as its own line.
- Letter-tracking on the name was considered but skipped — ReportLab doesn't expose per-character spacing cleanly enough to be worth it; 22pt bold is a strong enough anchor.

## Success Metrics — Verified

- Rendered PDF shows the name banner + accent rule + contact line + section rules + right-aligned dates (verified via real-run against `input/master_resume.example.yaml` + `input/facts_bank.example.yaml` + `input/job.txt`).
- `fitz.get_text` on the output returns single-column line-ordered text with each bullet on its own line (`• Led migration of monolith…`), no column mixing, no orphan `•` glyphs. ATS extraction intact.
- All 130 tests pass; added two new tests (`test_role_dates_extract_on_same_line_as_role`, `test_structure_survives_typography_changes`) asserting that the typography changes don't regress the text-content guarantees.

## The Change

By the end of this issue, the `default` template looks like something a recruiter would stop on instead of skim past, while the underlying PDF text stream is still the same single-column, selectable text that `parse_resume` / ATS scanners consume.

## Key Files

- `src/resume_operator/tools/pdf_generator.py` — template styles + `_render_default`
- `tests/test_pdf_generator.py` — add structural assertions for the new layout
- `docs/architecture.md` — note the template-tuning scope (no engine change)

## Dependencies

- #027 ✓

## Labels

`enhancement`, `priority:medium`
