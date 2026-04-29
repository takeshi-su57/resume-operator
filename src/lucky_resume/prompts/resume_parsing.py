"""Prompt template for resume PDF text parsing."""

PARSE_RESUME = """Extract structured data from the following resume text. The
goal is faithful ingestion, not summarization — preserve every bullet the source
shows.

Rules:
- Preserve every bullet verbatim. Do NOT summarize multiple bullets into one
  sentence. If a role has four bullets on the resume, the output must have four
  items in `bullets` for that role.
- Do NOT invent bullets that aren't in the source text.
- Do NOT truncate or merge bullets.
- Keep the wording close to the source; only fix obvious OCR artifacts.

Top-level fields:
- `name`, `email`, `phone`, `location`
- `headline` — a short tagline under the name if the resume shows one
  (e.g. "Senior Software Engineer · Founding Engineer · Ex-Google"). Empty
  string if the resume doesn't have a tagline.
- `summary` — the SUMMARY / PROFILE paragraph.
- `links` — list of {{label, url}} objects for any Portfolio / LinkedIn /
  GitHub / personal site links shown in the header.

Skills:
- `skills` — flat list of every skill mentioned.
- `skill_groups` — when the resume shows skills categorised (e.g.
  "Languages & Runtimes: Python, Go" and "Cloud & Infrastructure: AWS,
  Docker" as separate lines), extract each category as a {{category, items}}
  group. If the resume's skills are ungrouped, leave `skill_groups` empty
  and populate only `skills`.

For each experience entry, populate:
- `role`, `company`
- `start_date`, `end_date` — as they appear on the resume (e.g. "Aug 2023",
  "Present")
- `bullets` — one list item per source bullet
- `tech` — list of technologies shown explicitly as a `Tech: ...` line
  (or similar) at the bottom of the role's bullets. Empty list if the
  resume doesn't show one.

For each education entry, populate `degree`, `school`, `start_date`, `end_date`.

Leave unknown fields as empty strings rather than guessing.

Resume text:
{resume_text}
"""
