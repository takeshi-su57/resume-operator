"""Prompts for the `enrich` interactive session.

Two passes:
  - `ENRICH_QUESTIONS` — generate grounded questions the candidate can answer
    to fill gaps between their master resume and the target JD.
  - `ENRICH_POLISH` — rewrite the candidate's free-text answer into a single
    ATS-ready resume bullet, faithful to what they said.
"""

ENRICH_QUESTIONS = """You are helping a software engineer prepare for a specific job
application. You have their master resume and the target job description. Your
job is to identify gaps and ask the candidate {n_max} or fewer targeted questions
that, if answered, would strengthen the resume for THIS job.

Rules for questions:
1. Ground every question in something specific on the master resume AND/OR
   the job description. No generic questions like "do you have 8 years of
   experience?".
2. Ask for specifics the candidate can answer in 1-3 sentences: metrics,
   scope, stack, outcomes. Avoid yes/no questions.
3. One question per item — do NOT bundle multiple asks.
4. Do NOT draft bullets. Ask, don't tell. You are interviewing the candidate.
5. Avoid asking about items already captured in the facts bank.

For each question, include:
  - `area`: short tag like "role:exp-3" or "skill:AWS" or "jd:RESTful APIs"
  - `question`: the question, in second person ("Your Biblionexus bullet mentions…")
  - `why`: one line explaining why this matters for the JD

Master resume:
{master_yaml}

Existing facts bank:
{facts_yaml}

Job description:
{jd_text}
"""


ENRICH_POLISH = """The candidate just answered a resume-enrichment question in their
own words. Rewrite their answer as a single resume bullet that:

1. Starts with a strong past-tense action verb ("Built", "Led", "Shipped",
   "Designed", "Reduced", "Scaled", "Migrated").
2. Weaves in 1-2 relevant keywords from the job description naturally — no
   keyword stuffing.
3. Cites any metric, scope, or outcome the candidate mentioned. If they didn't
   give a metric, do NOT invent one.
4. Is one sentence, under 30 words. No filler phrases ("responsible for",
   "worked on", "helped with", "in charge of").
5. Is FAITHFUL to what the candidate said. Do NOT add headcount, duration,
   technology, metrics, or scope the candidate did not mention. Paraphrase,
   don't invent.
6. Is ATS-friendly — plain text, concrete, specific.
7. Uses plain ASCII punctuation — hyphens (`-`), straight quotes, `->`
   instead of `→`, three periods instead of `…`. No zero-width characters
   or placeholder ellipsis.

Also classify where this bullet belongs, using exactly one of these buckets:
  - `project`        — standalone project not tied to a specific role
  - `extra_bullet`   — a bullet that belongs under a specific role on the master;
                       MUST set `role_id` to one of the master role ids.
  - `skill`          — a single skill/technology (in that case `polished_text`
                       is just the skill name)
  - `certification`  — a certification (`polished_text` is the cert name)

If unsure between `project` and `extra_bullet`, prefer `extra_bullet` when the
answer clearly references a role from the master; otherwise prefer `project`.

Question asked: {question}
Candidate's raw answer: {answer}

Relevant context:
  - JD keyword hints: {jd_keywords}
  - Master role ids available for `role_id`: {role_ids}
"""
