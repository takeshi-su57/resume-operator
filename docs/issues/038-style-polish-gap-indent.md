# [Feature]: Style polish — name/headline gap, summary indent, bullet alignment

## Description

Five small style fixes from real-run feedback on the Consolas-rendered PDF:

1. **Name → headline gap** — currently the tagline touches the name. Add real vertical breathing room so the two read as distinct tiers.
2. **Summary first-line indent** — the SUMMARY paragraph should start with ~2 character-widths of whitespace on the first line (classic body-copy indent). Other sections stay flush.
3. **Role header alignment** — the role/company line in EXPERIENCE should align horizontally with the `EXPERIENCE` section header (both at the frame's left edge, zero indent).
4. **Bullet indent** — bullets should sit ~4 character-widths in from the role header. Current `left_indent=14pt` is ~2-3 chars in Consolas; bump to ~24pt for a cleaner visual hierarchy.
5. **Wrapped-bullet hanging indent** — when a bullet wraps, the continuation line should align vertically with the bullet's first character of text (not the bullet glyph). Already in place via `first_line_indent=-left_indent`; needs to scale with (4).

## Motivation

Direct user feedback after rendering with the Consolas style:

> *"double the gap between Title and highlight text. start 2 letter whitespace in the first line of summary and others looks good. in the experience section: role and company title start with vertically aligned with experience title. and bullet items should have a padding for 4 letters from experience in vertically. and if the bullet length over the line then each lines should be same position in vertically."*

All five are style knobs, so they belong in the StyleTemplate (#72). The `summary` fix needs one schema addition — a dedicated `TextStyle` slot so the first-line indent only affects the SUMMARY paragraph, not other places that use `body` (education, skills flow).

## Target State

### Schema addition

- `StyleTemplate.summary: TextStyle` — a new slot, defaults inheriting `body` values but with `first_line_indent = 14` (~2 character widths).

### Knob updates (both `style.default.yaml` and `style.consolas.yaml`)

- `name_style.space_after: 6` — gap between name and headline.
- `summary.first_line_indent: 14` — 2-letter indent on the first line.
- `bullet.left_indent: 24` + `bullet.first_line_indent: -24` — 4-char indent with hanging alignment.

### Renderer change

- The SUMMARY section paragraph now uses `styles["summary"]` instead of `styles["body"]`. Every other place that used `styles["body"]` (education, skills flow, virtual-bucket bodies) stays on `body`.

### Alignment check

The role header already renders with `leftIndent=0` inside a Table with `LEFTPADDING=0`, and section headers render with `leftIndent=0` too. Both should hit the frame's left edge. Verify visually; if there's a discrepancy, it's some default padding from ReportLab that needs explicit zeroing.

## Success Metrics — Verified

- `TestStylePolish74` pins all five changes (5 new tests); 231 total pass.
- Real-run rendered the PDF cleanly against Bruno's real data: `pdf_generator: completed … size=75431 bytes, style='consolas'`. No regression in Consolas font registration or fallback.
- SUMMARY paragraph gains `first_line_indent: 14` — visible in the ReportLab ParagraphStyle but not in text-extraction (which collapses whitespace); the visual indent shows when the PDF is opened normally.
- `body` style keeps `firstLineIndent=0` so education / skills flow / virtual buckets stay flush.
- Bullet `leftIndent=24, firstLineIndent=-24` — 4 char-widths indent with hanging alignment, verified by `test_bullet_indent_is_four_char_widths`.
- Role and section styles both have `leftIndent=0` — no relative offset between them.

## Known follow-up (not in this PR)

The tailor is currently under-optimizing — last run kept 71 of 77 items (frontend Vue3/Web3 bullets survived despite a backend JD). The `OPTIMIZE_CONTENT` prompt doesn't push hard enough on *dropping* irrelevant items. Will ship in a separate PR that tightens the prompt: more aggressive drop instructions, explicit "reject items that don't advance the JD's listed requirements", and possibly a post-guard that warns when the kept-ratio is above a threshold.

## Key Files

- `src/resume_operator/tools/style.py` — `StyleTemplate.summary` field
- `src/resume_operator/tools/pdf_generator.py` — SUMMARY uses `styles["summary"]`
- `input/style.default.yaml` — all 4 knob updates
- `input/style.consolas.yaml` — mirror
- `tests/test_style.py`, `tests/test_pdf_generator.py` — cover the new knobs

## Dependencies

- #72 (StyleTemplate infrastructure — this PR extends it)

## Labels

`enhancement`, `priority:medium`
