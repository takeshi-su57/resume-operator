# [Feature]: Senior-engineer resume format — tagline, categorized skills, per-role tech line, links

## Description

Inspired by reviewing Andy Wang's CV (\`input/andy-wang-cv.docx\`), four structural additions that bring the generated PDF closer to how senior-engineer resumes are actually laid out:

1. **Tagline / headline** under the name — e.g. *"Senior Software Engineer · Founding Engineer · Ex-Google"*. Currently nothing renders between name and contact, so the recruiter's eye has no hook.
2. **Categorized skills** — group skills by domain (Languages, Frontend, Backend, Cloud, AI/ML) instead of a single flat `·`-separated line. Today's skills section is a dump; Andy's is a scan-friendly table.
3. **Per-role tech line** — after each experience role's bullets, emit a dim italic `Tech: TypeScript, Nest.js, Docker, …` line. Low-effort ATS bonus + skim aid.
4. **Structured links** in the header — Portfolio / LinkedIn / GitHub as their own fields on a second contact line.

## Motivation

Direct user feedback on the rendered resume: *"the style of resume still not looks good"*. After the #66 hierarchy/sanitizer work, the remaining gap is structural — the current output is missing conventions recruiters now expect on a senior-engineer resume. Looking at a real well-built CV made the gap concrete: tagline, skill categories, and per-role tech lines are the format-level things that make an output read "senior" instead of "generic".

All four fixes are additive, not rewrites. Existing `master_resume.yaml` files stay loadable (missing fields default to empty); the renderer falls back gracefully when a field is empty.

## Target State

### `ResumeMaster` additions
- `headline: str = ""` — a short tagline rendered under the name
- `links: list[Link]` where `Link { label: str, url: str }` — rendered as a second contact line when non-empty
- `skill_groups: list[SkillGroup]` where `SkillGroup { category: str, items: list[str] }` — when non-empty, SKILLS renders grouped; otherwise falls back to the existing flat `skills: list[str]` rendering
- `ExperienceEntry.tech: list[str] = []` — rendered as a `Tech: …` line after the bullets

`ResumeData` stays as today — the new fields live on `ResumeMaster` only. `state.resume` (legacy view) still works for ats_score / analyze_gaps. A new `_build_master_from_llm(parsed)` helper in `parse_resume.py` constructs the `ResumeMaster` with the new fields directly, instead of routing through `resume_data_to_master`.

### Bootstrap prompt
`PARSE_RESUME` grows explicit instructions: extract a headline if one is present under the name, group skills by category where the source resume does so, extract per-role tech lists where the source shows them, and capture portfolio/LinkedIn/GitHub links as structured items. All fields are optional — the LLM leaves them empty when the source doesn't have them.

### Source index
`skill_groups` items get flattened into the source index with the same `master:skill:<name>` IDs, so the tailor's fabrication guard keeps working unchanged. Categories are purely a render concern.

`headline`, `links`, and `tech` are NOT added to the source_index — they're header/footer metadata, not items to be kept/reworded/dropped.

### Renderer
- Headline: 11pt, muted grey, rendered on a line directly below the name (before the accent rule)
- Links: second contact line below the first, `·`-separated, same muted grey style
- Tech line: emitted after a role's bullets, `Tech: A, B, C` in 9.5pt italic muted grey
- Skill groups: each group renders as `**Category**: item1, item2, item3` on its own line; flat skills fallback unchanged when groups are empty

### Example YAML refresh
`input/master_resume.example.yaml` gets a light rewrite to demonstrate every new field, so future bootstrap users have a reference.

## Success Metrics — Verified

Real-run against the refreshed `input/master_resume.example.yaml` (seeded
with headline, links, skill_groups, per-role tech) rendered the following
extracted text, in order:

```
Jane Smith
Senior Software Engineer · Founding Engineer · Ex-Acme
jane.smith@example.com · +1 555 123 4567 · San Francisco, CA
Portfolio: https://janesmith.example · LinkedIn: linkedin.com/in/jane-smith · GitHub: github.com/jsmith
SUMMARY
…
EXPERIENCE
Senior Software Engineer — Acme Corp
Remote · 2021-03 - present
• Led migration of monolith to Go microservices, cutting p99 latency 40%.
• …
Tech: Go, gRPC, Kubernetes, PostgreSQL, Prometheus
…
SKILLS
Languages & Runtimes: Go, TypeScript, SQL
Frontend & APIs: React, REST
Backend & Data: PostgreSQL, gRPC
Cloud & Infrastructure: AWS, Kubernetes, Docker
```

Every `#68` addition visible and in the expected position.

Back-compat verified against Bruno's real `data/master_resume.yaml` (which
has no headline / links / skill_groups / per-role tech — the LLM correctly
left them empty): the pipeline still renders a valid PDF with the flat
skills line, no tagline, no second contact line, and no tech lines. The
new fields are additive — absent-is-fine.

Test coverage:
- `TestSeniorFormatFields` (7 cases) covers render paths for all four
  fields + their empty/fallback behaviours.
- `TestSkillIndexing` (3 cases) covers flat, grouped, and mixed flat+grouped
  indexing into `master:skill:<name>` IDs.
- `TestSeniorFormatExtraction` (2 cases) covers the bootstrap
  `_build_master_from_llm` path: rich extraction populates every field,
  sparse LLM output defaults every field to empty.
- 180 tests pass overall (13 new vs. pre-#68 baseline).

## Key Files

- `src/resume_operator/state.py` — `Link`, `SkillGroup`, `ResumeMaster.headline`/`.links`/`.skill_groups`, `ExperienceEntry.tech`
- `src/resume_operator/nodes/parse_resume.py` — LLM schema extensions + `_build_master_from_llm` helper
- `src/resume_operator/prompts/resume_parsing.py` — extraction guidance for the four new fields
- `src/resume_operator/tools/source_index.py` — flatten `skill_groups` into the index
- `src/resume_operator/tools/pdf_generator.py` — four new render paths; `skill_groups` + flat-fallback; headline/links/tech
- `input/master_resume.example.yaml` — showcase the new format
- `tests/test_pdf_generator.py`, `tests/test_parse_resume.py`, `tests/test_source_index.py` (if new) — schema round-trip, render, back-compat, index flattening

## Dependencies

- #024 (master YAML contract), #026 (source_index + fabrication guard), #66 (hierarchy + sanitizer — this PR extends that template)

## Labels

`enhancement`, `priority:high`
