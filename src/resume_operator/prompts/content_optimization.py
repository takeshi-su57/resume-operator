"""Prompt template for resume content optimization — per-item tailoring."""

OPTIMIZE_CONTENT = """You are tailoring a candidate's resume for a specific job.

Your job is a *per-item* decision over a menu of source items. You MAY NOT
invent new bullets or skills — you may only keep, reword, or drop existing
ones from the menu below.

=== SOURCES MENU ===
Every item you reference in your output MUST use the exact `source_id` from
this menu. An output item whose `source_id` is not in this menu will be
rejected.

{source_menu}

=== JOB DESCRIPTION ===
{job_description}

=== GAP ANALYSIS (from earlier pass) ===
{gap_analysis}

=== YOUR TASK ===
Return a list of `TailoredItem` decisions covering the items that belong in
the tailored output. Each item:

- `source_id` — exact match to a menu entry above
- `action` — one of:
  - `keep`   → include the source text unchanged
  - `reword` → include, but rephrased for this JD; fill `new_text`
  - `drop`   → the item was considered but excluded from the final resume
- `original_text` — echo the source text so the diff reader has context
- `new_text` — only when action is `reword`; otherwise leave empty

Include `drop` decisions for items from the master that you chose NOT to
include — the reader wants to see what was cut, not just what was kept.

Pull in items from the facts bank (source_id starting with `facts:`) only
when they strengthen the match for this specific JD.

Add short free-form `notes` explaining the overall strategy (what you
emphasized, what you downplayed, and why).
"""
