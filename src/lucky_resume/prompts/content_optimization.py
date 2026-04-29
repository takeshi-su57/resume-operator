"""Prompt template for resume content optimization — per-item tailoring."""

OPTIMIZE_CONTENT = """You are tailoring a candidate's resume for a specific job.

Your job has three parts:

### Part 0 — Tailored headline

Write a short JD-weighted tagline that sits directly under the candidate's
name on the tailored resume. Rules:
- 10-15 words max. 2-4 identity tags separated by ` · ` (space, middle dot,
  space). Example shape: "Senior Backend Engineer · 10+ years · Node.js, AWS".
- Grounded STRICTLY in master facts — titles the candidate actually held,
  years they can show, companies they actually worked at, tech the master
  lists. Do NOT invent "Ex-Google" unless Google is on the master. Do NOT
  invent years or specialisations.
- Weighted toward the JD. A backend JD should yield a backend-leaning
  headline; an AI role should surface AI/ML tags the master supports.
- Return as the `tailored_headline` field of the output.

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

### Part 2 — Per-item decisions (be aggressive about dropping)

This is the hardest part and the one where you are most likely to go wrong
by being too permissive. DEFAULT TO DROPPING. The tailored resume should
look focused on THIS specific JD, not like a catalog of everything the
candidate has ever done.

Decision rules:

- **KEEP** — the item directly supports a listed JD requirement (stack,
  responsibility, domain). Current and recent roles that match the JD's
  domain. Skills/certs explicitly named or near-named in the JD.

- **REWORD** — the item supports the JD but the wording doesn't surface
  that fit. Rewrite to lead with the JD-relevant keyword while staying
  faithful to what the candidate actually did. Fill `new_text`.

- **DROP** — the item doesn't advance THIS JD. Be ruthless here. Common
  cases you MUST drop:
    * Frontend-only bullets for a backend JD (and vice versa)
    * Domain-specific work the JD doesn't touch — e.g. Web3 / crypto /
      NFT / smart contracts for a traditional SaaS backend JD
    * Older tech stacks the JD doesn't mention (PHP, Solidity, jQuery,
      Ruby on Rails, etc. — unless the JD asks for them)
    * Experimental / personal / side-project work that doesn't match
      the JD's industry or scale
    * Roles older than the candidate's last 3-4 most recent — unless
      they uniquely cover a JD-required skill nothing newer does
    * Skills the candidate lists but the JD doesn't care about — a
      skills section with 20 entries reads as unfocused; 8-10 tight
      matches reads as targeted

Target: a one-page tailored resume. That typically means 4-8 bullets
across the 2-4 most recent roles, plus a tight skills section (8-12
relevant entries), education, and certs. Everything else should be
`drop`, not `keep`.

**Self-check before returning**: count your `keep` + `reword` items
across the SOURCES MENU. If more than ~50% of the menu ends up
kept+reworded, you are almost certainly being too permissive — go back
and drop more. A backend-specific JD applied to a mixed Web3/frontend
master should typically drop 50-70% of the items.

Every item you reference MUST use the exact `source_id` from the menu
below. An output item whose `source_id` is not in this menu will be
rejected. Items you decide to drop should appear in the output as
`action: "drop"` — that way the diff.md shows the reader what was
considered and cut (not silently omitted).

=== SOURCES MENU ===
{source_menu}

=== JOB DESCRIPTION ===
{job_description}

=== GAP ANALYSIS (from earlier pass) ===
{gap_analysis}

### Output schema

Return a `TailoredResumeLLMOutput` with:
- `tailored_headline` — the tagline from Part 0 (string)
- `tailored_summary` — the fresh summary from Part 1 (string)
- `items` — list of per-item decisions (see below); do NOT include a
  `master:summary` entry here.
- `notes` — short free-form strategy notes explaining what you emphasized,
  what you downplayed, and specifically which domains/roles you dropped
  because the JD didn't need them.

Each `item`:
- `source_id` — exact menu match
- `action` — `keep` (include unchanged), `reword` (include with new phrasing),
  or `drop` (considered but excluded from output)
- `original_text` — echo the source for context
- `new_text` — only when action is `reword`

Pull in `facts:*` items only when they strengthen the match for this
specific JD. Same aggressive-drop rule applies — a facts item that
doesn't advance THIS JD should be `drop`, not `keep`.

### Output style

Use plain ASCII punctuation in `tailored_headline`, `tailored_summary` and
`new_text`:
- Hyphens (`-`), not en-dashes or non-breaking hyphens
- Straight quotes (`"` and `'`), not curly
- `->` instead of `→`; `...` instead of `…`
- The one exception: in `tailored_headline`, use the middle-dot `·` (U+00B7)
  between tags. That character IS in the renderer's font.

The rendered PDF's default font doesn't carry exotic Unicode glyphs and would
render them as black boxes; keep the wording portable.
"""
