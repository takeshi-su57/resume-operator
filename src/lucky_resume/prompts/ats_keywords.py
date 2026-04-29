"""Prompts for the #81 keyword-extraction pass.

One LLM call extracts hard skills (tools, languages, frameworks, cloud
services) and soft skills (leadership, problem solving, collaboration)
from BOTH the resume text and the JD text in a single prompt. The
downstream comparison is deterministic — we count occurrences per skill
in each document and assemble the side-by-side table that industry ATS
reviewers surface.
"""

EXTRACT_ATS_KEYWORDS = """You are extracting ATS-relevant keywords from a candidate's
resume and a job description. Your output feeds a side-by-side skill-count
table (industry ATS reviewers' "match rate" view).

### Rules

1. **Two categories only**: `hard_skills` (tools, languages, frameworks,
   cloud services, named technologies — e.g. "Python", "Kubernetes",
   "PostgreSQL") and `soft_skills` (mentoring, problem solving, leadership,
   collaboration, communication).

2. **Canonical naming**: use a single canonical form per skill, case-
   sensitive matches only. If the resume says "TypeScript" and the JD says
   "Typescript", pick the more common form ("TypeScript") and report the
   combined count. If the resume says "K8s" and the JD says "Kubernetes",
   pick "Kubernetes" and collapse them.

3. **No synonyms explosion**: don't list "JavaScript" AND "JS" AND
   "ECMAScript" separately. Pick one.

4. **Count carefully**: `resume_count` is how many distinct mentions of
   the skill appear in the resume text; `jd_count` is the same for the JD.
   A skill mentioned once in a bullet and once in the skills list is 2
   mentions. A skill appearing only in one document has a 0 on the other
   side — that's what gets flagged as a gap.

5. **Skip trivia**: don't extract generic words like "software", "system",
   "product", "engineer" — they're noise. Focus on named technologies and
   named competencies.

6. **Cap the output**: at most 25 hard skills and 15 soft skills. If
   there are more, prioritize: highest-count-in-the-JD first.

### Output schema

Return an `ATSKeywordsLLMOutput` with:
- `hard_skills` — list of `{{name, resume_count, jd_count}}` rows
- `soft_skills` — list of `{{name, resume_count, jd_count}}` rows

=== RESUME TEXT ===
{resume_text}

=== JOB DESCRIPTION ===
{jd_text}
"""
