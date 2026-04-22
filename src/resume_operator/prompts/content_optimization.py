"""Prompt template for resume content optimization — per-item tailoring."""

OPTIMIZE_CONTENT = """You are tailoring a candidate's resume for a specific job.

Your job has two parts:

### Part 1 — Tailored summary

Write a fresh 2-3 sentence SUMMARY opener for this resume, weighted toward
the JD below. Rules:
- Grounded ONLY in facts derivable from the sources menu (years of experience,
  tech stacks, role seniority). Do NOT invent metrics, headcount, tech, or
  scope that isn't in the menu.
- Active voice, specific, JD-aligned. Avoid filler like "results-driven" or
  "passionate about X".
- Return as the `tailored_summary` field of the output.
- Do NOT also include `master:summary` in the `items` list below — the
  dedicated field owns the summary.

### Part 2 — Per-item decisions

For every other master/facts item, decide keep / reword / drop. Every item
you reference MUST use the exact `source_id` from the menu below. An output
item whose `source_id` is not in this menu will be rejected.

=== SOURCES MENU ===
{source_menu}

=== JOB DESCRIPTION ===
{job_description}

=== GAP ANALYSIS (from earlier pass) ===
{gap_analysis}

### Output schema

Return a `TailoredResumeLLMOutput` with:
- `tailored_summary` — the fresh summary from Part 1 (string)
- `items` — list of per-item decisions (see below); do NOT include a
  `master:summary` entry here.
- `notes` — short free-form strategy notes explaining what you emphasized,
  what you downplayed, and why.

Each `item`:
- `source_id` — exact menu match
- `action` — `keep` (include unchanged), `reword` (include with new phrasing),
  or `drop` (considered but excluded from output)
- `original_text` — echo the source for context
- `new_text` — only when action is `reword`

Pull in `facts:*` items only when they strengthen the match for this
specific JD.

### Output style

Use plain ASCII punctuation in `tailored_summary` and `new_text`:
- Hyphens (`-`), not en-dashes or non-breaking hyphens
- Straight quotes (`"` and `'`), not curly
- `->` instead of `→`; `...` instead of `…`
The rendered PDF's default font doesn't carry those exotic glyphs and would
render them as black boxes; keep the wording portable.
"""
