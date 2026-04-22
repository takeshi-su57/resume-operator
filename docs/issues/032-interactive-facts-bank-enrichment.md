# [Feature]: Interactive `enrich` command — LLM asks, you answer, LLM polishes, facts_bank grows

## Description

When the master resume is thin against a target JD, the tailor can't do its job — `run` ends up with a sparse output because there's nothing to keep/reword/drop. Rather than asking the LLM to draft bullets (which invites fabrication), add an interactive enrichment session where the LLM asks grounded questions, you answer in your own words, and the LLM polishes your answer into an ATS-ready bullet that you accept, edit, or reject. Accepted items land permanently in `facts_bank.yaml` so future tailoring runs inherit them.

## Motivation

Observed directly when running the pipeline against the real `input/resume.pdf` + `input/job.txt`: the master has one-bullet-per-role (fixed in #60) but still lacks the specific metrics / scope / stack detail that a Staff Backend JD needs. The tailor kept only 6 items and dropped the current role entirely. The root cause isn't the prompt — it's missing source material.

The dangerous shortcut is "have the LLM draft bullets you approve". That's fabrication-prone: if the LLM writes *"Reduced API latency 40% at Hilolabs"* and you skim-approve, that's now a claim on your resume. The defensible shape is: LLM asks questions grounded in your master + the JD, you answer in free text, LLM polishes phrasing only. Facts stay yours; only grammar and ATS-keyword placement come from the model.

## Target State

After this change:

1. New CLI command: `resume-operator enrich --master M.yaml --facts F.yaml --job J.txt [--max-questions 5] [--dry-run]`
2. The session flow:
   - Load master + facts + JD. Build a `SourceIndex` so the LLM knows what's already captured.
   - **Question generation pass**: LLM returns up to `N` questions, each grounded in a specific gap between master/facts and JD. Structured output via `with_structured_output` — no manual JSON parsing. Dry-run stops here and prints them.
   - **Interactive loop** for each question:
     1. Print the question + a one-line "why this matters".
     2. Prompt for a free-text answer (or `skip`/`quit`).
     3. **Polish pass**: LLM takes the raw answer + JD keywords + master context, returns `(polished_bullet, suggested_bucket, suggested_role_id)`. Polished text is one sentence, active verb, JD keywords woven in, no redundant filler. Faithful to the answer — no added metrics, headcount, or tech the candidate didn't mention.
     4. Show the polished bullet + bucket suggestion.
     5. Prompt: `[a]ccept / [e]dit / [r]eject / [s]kip / [q]uit`. Edit lets you type new text; that text becomes final (no further polish).
   - **Persist**: accepted items append to `facts_bank.yaml` in the LLM-suggested bucket (`projects`, `extra_bullets[role_id]`, `skills_beyond_master`, `certifications_beyond_master`). Each new item carries a `source: "enrich YYYY-MM-DD"` metadata field so you can trace it later.
3. `FactItem` schema gains an optional `source: str = ""` field.
4. `tools/facts_bank.py` gains `append_to_facts(path, new_items)` — loads existing content, merges new items into the right buckets, dumps back with unique IDs and canonical ordering.

## Success Metrics — Verified

Real-run proof: `enrich --dry-run` against the bootstrapped master +
`input/job.txt` (Foodsmart Staff Backend role) produced 5 grounded questions.
Every single one references specific content on the master and ties to a
stated JD requirement — no generic "do you have 8 years of experience?"
questions. Sample:

> *"Your Biblionexus bullet mentions enhancing database performance through
> indexing and normalization. Can you quantify how much you improved query
> response times or overall system efficiency?"*
> why: Quantifying performance improvements demonstrates your impact and
> expertise in database management, which is crucial for the backend role.

> *"You mentioned automating cloud infrastructure configuration using
> Terraform. Can you share more about the specific AWS services you used
> and any metrics on time saved or efficiency gained?"*
> why: AWS experience is vital for this position, and specific metrics
> will strengthen your application.

All five questions follow the same shape: concrete reference to master
content + JD-specific motivation.

Other acceptance criteria covered by unit tests (151 total after this PR):
- `TestAssembleAdditions` — bucket routing, unique ID minting with collision
  avoidance against an existing facts bank, `source` stamping.
- `TestAppendToFacts` — creates file if missing, preserves existing items,
  dedupes scalar skills, handles ID collisions (last write wins).
- `TestPolishAnswer.test_demotes_to_project_when_role_id_unknown` — guards
  against the LLM asserting `extra_bullet` with a made-up role_id.
- `TestEnrichCommand.test_dry_run_prints_questions_no_prompts` — dry-run
  never writes the facts bank.
- `TestEnrichCommand.test_full_session_writes_accepted_item` — end-to-end
  with mocked LLM + piped stdin, verifies the polished text lands in
  `facts_bank.yaml` with the `source` stamp.

## The Change

By the end of this issue, when tailoring comes back thin, the user can run an interactive interview with the LLM that grows `facts_bank.yaml` durably. Next time that JD-or-similar comes around, the tailor has real material to choose from without a second interview. The resume operator stops being a one-shot tool and starts being a career-facts store that compounds over time.

## Key Files

- `src/resume_operator/state.py` — `FactItem.source: str = ""`
- `src/resume_operator/tools/facts_bank.py` — `append_to_facts(path, new_items)`
- `src/resume_operator/tools/enrich.py` (new) — schemas + LLM calls + interactive session
- `src/resume_operator/prompts/enrich.py` (new) — question and polish prompts
- `src/resume_operator/main.py` — `enrich` command wiring
- `tests/test_enrich.py` (new) — mocked LLM + mocked stdin, covers session outcomes

## Dependencies

- #024 ✓ (master YAML + facts bank contract)
- #025 ✓ (facts bank exists)
- #026 ✓ (SourceIndex — used to tell the LLM what's already captured)
- #028 ✓ (structured output — used for both question and polish schemas)
- #60  ✓ (master preserves bullets — the enrich flow only makes sense when the master isn't a summary)

## Labels

`enhancement`, `priority:high`
