# [Refactor]: Multi-dimensional ATS scoring aligned with industry ATS reviewers

## Description

Our `ats_score` node today produces a single `ATSScore { score: 0.0..1.0, reasoning, keyword_matches, keyword_gaps }`. The LLM is asked *"how well does this resume match this JD, in one number"* and returns a blob. Real ATS review products (JobScan, Resumeworded, Talenthack, etc.) produce a structured multi-dimensional report:

- **Contact information** — is there an address, email, phone? (Deterministic, no LLM.)
- **Section headings** — Education / Experience / Summary present? (Deterministic.)
- **Job title match** — does the exact JD title appear on the resume? (Deterministic string match.)
- **Date formatting** — are dates in a consistent parseable format? (Deterministic regex.)
- **File type / filename** — `.pdf` preferred, concise filename. (Deterministic.)
- **Hard-skill match table** — per-skill count on resume vs. JD, side by side. (Deterministic with a named-skill extractor.)
- **Soft-skill / keyword match** — same table for soft skills. (LLM-assisted extraction, deterministic comparison.)
- **Job level match** — years of experience alignment. (LLM-assisted.)
- **Measurable results count** — number of bullets with quantified impact. (Deterministic regex for numbers + `%`/`$`/`x`.)
- **Resume tone** — flag cliches and negative phrases. (LLM-assisted.)
- **Word count** — inside the recommended 400–1000 range. (Deterministic.)
- **Font / layout / page setup** — for rendered PDFs, standard fonts, left-aligned, standard margins. (Deterministic via PDF metadata.)

The current single-number score hides all of this. Two problems follow:

1. **The #44 skip gate fires on a misleading number.** A garbage LLM response claiming `score=1.00` bypasses optimization entirely. The threshold is a blunt instrument over a noisy signal.
2. **The user sees less actionable feedback than an external ATS review would give.** They get *"score=0.73, reasoning: strong Python match but missing Kubernetes"* instead of a structured report they can act on line by line.

## Motivation

Direct user observation, after comparing our `ats_score` output against an external ATS review:

> "btw, it looks like your ats system isn't correct when compare to the industry default"

External review output showed per-dimension pass/fail + keyword-count tables + tone flags. Our output is a float and a paragraph. Bridging that gap is a natural second pass now that #78 has given us the loop machinery — a richer score makes the loop's user-gate more meaningful (*"your contact info is incomplete AND your Kubernetes-count is 0 vs. JD's 5"* beats *"0.73"*).

## Target State

### Schema: `ATSReport` replaces the single-dimensional `ATSScore`

```python
class ContactCheck(BaseModel):
    email_present: bool
    phone_present: bool
    address_present: bool

class SectionCheck(BaseModel):
    summary: bool
    experience: bool
    education: bool
    skills: bool

class JobTitleMatch(BaseModel):
    exact_match: bool
    partial_match: bool  # fuzzy/substring
    jd_title: str
    resume_titles: list[str]

class SkillCountRow(BaseModel):
    name: str
    resume_count: int
    jd_count: int

class ToneFlag(BaseModel):
    phrase: str          # e.g. "results-driven"
    line: str            # surrounding context
    suggestion: str      # e.g. "Replace with a specific result"

class ATSReport(BaseModel):
    # Composite numeric score — derived, NOT the primary output
    composite_score: float

    # Structural checks (deterministic)
    contact: ContactCheck
    sections: SectionCheck
    job_title: JobTitleMatch
    measurable_results_count: int
    word_count: int
    word_count_ok: bool  # within 400-1000

    # Keyword analysis (LLM-assisted extraction, deterministic comparison)
    hard_skills: list[SkillCountRow]
    soft_skills: list[SkillCountRow]

    # Qualitative (LLM)
    tone_flags: list[ToneFlag]
    level_match_reasoning: str

    # Back-compat fields (old callers read these)
    score: float          # alias of composite_score
    reasoning: str        # human-readable summary
    keyword_matches: list[str]  # derived from hard_skills + soft_skills
    keyword_gaps: list[str]
```

### Split deterministic and LLM passes

- **`tools/ats_checks.py`** (NEW) — pure-Python checks: contact-info regex, section-heading detection, job-title exact-match, date-format validation, measurable-results count (regex for `\d+%`, `\$\d`, `\d+x`, etc.), word count. No LLM.
- **`tools/ats_keyword_extractor.py`** (NEW) — single LLM call that returns `{hard_skills: [...], soft_skills: [...]}` for both the resume text and the JD text. Deterministic comparison produces the count table.
- **`tools/ats_tone_checker.py`** (NEW) — single LLM call flagging cliches/negative phrases. Returns `list[ToneFlag]`.
- **`nodes/ats_score.py`** — orchestrates the three, assembles into `ATSReport`, derives `composite_score` from weighted sub-scores.

### Composite score formula

Empirical weighting, tunable via config. Starting point (sums to 1.0):
- 0.40 — hard-skill match (coverage of JD skills)
- 0.20 — soft-skill match
- 0.15 — structural completeness (contact + sections + word count)
- 0.10 — job-title match
- 0.10 — measurable results (normalized against a target, say 8)
- 0.05 — tone score (1.0 minus a penalty per flag)

`ATS_SCORE_WEIGHTS_*` env vars override each one so the user can tune.

### CLI output

`score` command displays the structured report as a Rich `Table`:

```
┌─────────────────────┬──────────┬─────────────────────────────────────┐
│ Dimension           │ Status   │ Detail                              │
├─────────────────────┼──────────┼─────────────────────────────────────┤
│ Contact info        │ ⚠        │ phone missing                       │
│ Section headings    │ ✓        │ all present                         │
│ Job title match     │ ✗        │ 'Senior Full-Stack LLM Engineer'    │
│                     │          │ not in resume                       │
│ Hard skills         │ 18 / 24  │ Kubernetes (0/5), AWS Lambda (0/3)  │
│ Measurable results  │ ✓  11    │ target 5+                           │
│ Word count          │ ✓  742   │ within 400-1000                     │
│ Tone flags          │ ⚠  2     │ "results-driven", "passionate"      │
└─────────────────────┴──────────┴─────────────────────────────────────┘
Composite: 0.68
```

`run` keeps its concise single-line display (composite + top-3 gaps) but the full report lives in `results.json`.

### #78 integration

The approval loop's user gate today shows:
```
Iteration 1/3: ATS score on tailored output = 73%
```

After this refactor it shows:
```
Iteration 1/3: composite 73%  |  hard skills 14/22  |  missing: K8s, Lambda, RDS, DynamoDB
```

Much more actionable. `propose_changes` also sees the structured report and can target proposals at specific gap dimensions ("JD has 5 mentions of Kubernetes, resume has 0 — propose a bullet that legitimately surfaces K8s from your Docker experience").

### Back-compat

The old `ATSScore` class stays as an alias so pre-refactor callers don't break:
```python
ATSScore = ATSReport  # the composite score lives on both names
```

All the old fields (`score`, `reasoning`, `keyword_matches`, `keyword_gaps`) remain on `ATSReport` for one-release compatibility, marked deprecated. Remove in the release after.

### #44 skip gate

Today: `state.ats_score.score >= 0.9 → skip optimize_content`.
After: `state.ats_score.composite_score >= threshold AND no dimension critically low`. A run where every soft dimension is 1.0 but `hard_skills` shows 2/20 shouldn't skip. Add per-dimension minimums alongside the composite.

## Success Metrics

- Running `score` against Takeshi's master + the Foodsmart JD produces a per-dimension table that matches the external ATS review within a reasonable tolerance (exact numbers won't align across vendors, but the *dimensions present* should match).
- The #44 skip gate no longer fires on garbage LLM output: a float returned outside the 0.0–1.0 range, or a composite score that doesn't survive the per-dimension minimum check, means the optimize path runs regardless.
- `results.json` grows a structured `ats_report` object inspectable by downstream tooling (a potential LuckyPlans dashboard).
- 10+ new tests cover the deterministic checks individually (contact regex, section heading detection, job-title fuzzy match, measurable-results regex, word count bounds) plus integration tests for the composite assembly.
- No regression on existing `ats_score` callers during the one-release back-compat window.

## Key Files

- `src/resume_operator/state.py` — `ATSReport`, sub-models, back-compat alias.
- `src/resume_operator/nodes/ats_score.py` — orchestration.
- `src/resume_operator/tools/ats_checks.py` (NEW) — deterministic checks.
- `src/resume_operator/tools/ats_keyword_extractor.py` (NEW) — LLM keyword extraction.
- `src/resume_operator/tools/ats_tone_checker.py` (NEW) — LLM tone flags.
- `src/resume_operator/prompts/ats_keywords.py` (NEW) — extraction prompt.
- `src/resume_operator/prompts/ats_tone.py` (NEW) — tone prompt.
- `src/resume_operator/main.py` — Rich `Table` display in `score` command, concise line in `run`.
- `src/resume_operator/config.py` — per-dimension weights + minimums env vars.
- `src/resume_operator/graph.py` — if `ats_score` splits across multiple nodes, wire the subgraph.
- `tests/test_ats_checks.py`, `tests/test_ats_keyword_extractor.py`, `tests/test_ats_tone_checker.py`, `tests/test_ats_score.py` (extended).

## Dependencies

- **#78** (iterative approval loop) — optional but shapes this work; the loop's user-gate display and `propose_changes` prompt should consume the structured report rather than the single number.
- Related to #039 (aggressive-drop prompt) and #76 (kept-ratio guard) — those add guardrails around optimize_content; this adds the same pattern around ats_score.

## Out of Scope

- **PDF-format checks** (font name / margin / layout). Requires parsing the rendered PDF bytes, which is a separate investigation into ReportLab metadata.
- **Headless ATS simulation** — actually running the resume through a named commercial ATS. That's a different beast: vendor APIs, quota management, probably a paid service.
- **Real-time scoring during typing** — a live-preview UX is out of scope; we're fine with the batch `score` / `run` invocations.

## Labels

`refactor`, `enhancement`, `priority:medium`
