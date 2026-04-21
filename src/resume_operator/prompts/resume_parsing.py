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

For each experience entry, populate:
- `role`, `company`
- `start_date`, `end_date` — as they appear on the resume (e.g. "Aug 2023",
  "Present")
- `bullets` — one list item per source bullet

For each education entry, populate `degree`, `school`, `start_date`, `end_date`.

Leave unknown fields as empty strings rather than guessing.

Resume text:
{resume_text}
"""
