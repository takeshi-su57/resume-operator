# [Feature + Refactor]: Tailored summary, typographic hierarchy, and Unicode sanitizer

## Description

Three related PDF-output issues surfaced from real-world use. Bundle them into one PR because they all touch the `generate_pdf` path:

1. **Per-JD summary rewrite** — the summary currently rides the same `keep/reword/drop` rails as any other item via `master:summary`, which limits how far it can pull toward the JD. A fresh 2-3 sentence JD-tailored summary, grounded in the master, is what recruiters actually scan for.
2. **Font + size hierarchy** — current sizes are name 22pt → section 10.5pt → role 10.5pt → body 10pt. Section headers and role titles are the same size as body text; the eye reads the page flat because there's no clear tier structure. "Font doesn't look professional" is almost always a hierarchy problem, not a face problem.
3. **Unicode sanitizer** — Helvetica uses Adobe Standard Encoding, which doesn't cover exotic Unicode (`→`, `‑`, `‑`, `…`, zero-width spaces). When the LLM emits those, ReportLab draws the `.notdef` black square. Observed in real runs already: arrows like "Node.js 14 → 18" and hidden U+200B in enrichment-polished text.

## Motivation

Direct user quotes: *"summary of resume should be rewritten everytime with master summary + job description"*, *"the font isn't look professional"*, *"it looks like you tried to add - for connect two words, but currently it renders square box in black filled"*. All three are one-line-feedback-able for the user but each unfixes a different failure mode on the rendered PDF.

## Target State

1. **`TailoredResume` gains a `tailored_summary: str` field.** `optimize_content` LLM schema gets the same field; the prompt asks for a fresh JD-tailored summary in 2-3 sentences, strictly grounded in the master (no invented metrics, years, or tech). `optimize_content` prompt also now forbids `master:summary` in the items list — the dedicated field carries the summary instead, so it doesn't get double-rendered.
2. **PDF renderer uses `tailored_summary` when non-empty.** Falls back to the master-summary-keep-item behavior when the field is empty (e.g., older tailored.yaml from before this PR).
3. **Typographic hierarchy**:
   - Name: **24pt** (from 22pt) bold
   - Section headers: **12pt** (from 10.5pt) bold — the primary visual landmark gets its own tier
   - Role title: **11pt** (from 10.5pt) bold — sub-tier below section
   - Role dates: 9.5pt muted grey (unchanged)
   - Body / bullets: 10pt (unchanged)
   - Space before section headers: 12pt (from 8pt) — clearer section breaks
4. **`_sanitize_for_pdf(text)` helper** applied to every string the renderer converts to a Paragraph / Table cell. Translation table:
   - Dashes: `‑` `–` `−` → `-` (em-dash `—` kept — it's in Helvetica)
   - Arrows: `→` → `->`, `←` → `<-`, `⇒` → `=>`, `⇐` → `<=`
   - Quotes: `'` `'` → `'`, `"` `"` → `"`
   - Ellipsis: `…` → `...`
   - Non-breaking space: ` ` → ` `
   - Strip: zero-width space (U+200B), ZWNJ (U+200C), ZWJ (U+200D), BOM (U+FEFF), soft hyphen (U+00AD), word joiner (U+2060)
   - Collapse runs of whitespace
5. **Prompt guidance in `optimize_content` and `enrich_polish`**: "Use plain ASCII punctuation — hyphens, straight quotes, `->` instead of arrows, three periods instead of ellipsis." Reduces the sanitizer's workload and keeps `tailored.yaml` readable.

## Success Metrics — Verified

Real-run against the bootstrapped master + `input/job.txt` (Foodsmart Staff
Backend) with `LLM_MODEL=openai/gpt-4o-mini --no-enrich`:

- `optimize_content: completed — items=77 (kept=11, reworded=1, dropped=65), fabricated_rejected=0, notes=3, summary=yes`. The log's `summary=yes` flag is the new field (#66) reporting that `tailored_summary` was populated.
- The rendered SUMMARY section of the PDF reads: *"Experienced lead Software Engineer with over 8 years in backend development, specializing in Node.js, TypeScript, and RESTful API design. Proficient in optimizing database performance and implementing CI/CD practices, bringing proven skills in building reliable systems and enhancing application scalability."* — backend-weighted, specific to the JD, not the generic master summary.
- Extracted text shows plain ASCII everywhere: `"2023 - January 2024"` (hyphen, not en-dash), `"Bachelor's Degree"` (straight quote, not curly). No residual arrows, non-breaking hyphens, or zero-width characters.
- 167 tests pass (13 new): `TestSanitizeForPdf` covers 7 translation/strip/preserve cases; `TestTypographicHierarchy` pins the tier structure so future edits can't silently flatten it; `TestTailoredSummaryRender` covers 3 paths including the "tailored summary replaces master summary" case.
- `diff.md` now opens with a `## Tailored Summary (fresh, JD-crafted)` block so the reader can audit the summary alongside the per-item changes.

## Key Files

- `src/resume_operator/state.py` — `TailoredResume.tailored_summary: str`
- `src/resume_operator/nodes/optimize_content.py` — LLM schema + projection
- `src/resume_operator/prompts/content_optimization.py` — summary request + ASCII guidance
- `src/resume_operator/prompts/enrich.py` — ASCII guidance in polish prompt
- `src/resume_operator/tools/pdf_generator.py` — sanitizer + hierarchy tune + tailored_summary render path
- `src/resume_operator/tools/diff_renderer.py` — surface the tailored summary in `diff.md` so it's reviewable
- `tests/test_pdf_generator.py` — sanitizer + hierarchy tests
- `tests/test_optimize_content.py` — tailored_summary round-trip

## Dependencies

- #026 ✓ (TailoredResume exists)
- #027 ✓ (deterministic render — sanitizer slots in there cleanly)
- #030 ✓ (default template — hierarchy tune extends it)

## Labels

`enhancement`, `refactor`, `priority:high`
