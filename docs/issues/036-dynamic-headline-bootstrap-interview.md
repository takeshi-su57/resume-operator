# [Feature]: Dynamic JD-tailored headline + interactive bootstrap interview

## Description

Two related changes, shipped together:

1. **Dynamic headline per JD.** `master.headline` is a static field today — every application you send gets the same tagline, which defeats the purpose. Mirror the `tailored_summary` pattern: add `TailoredResume.tailored_headline` that the `optimize_content` LLM crafts fresh per run, grounded in master facts. The renderer prefers the tailored headline when set; `master.headline` becomes an optional fallback for score-only runs or when the tailor doesn't emit one.

2. **Bootstrap interview for missing fields.** Parsing a PDF often leaves the senior-format fields (headline, links, per-role tech, skill_groups) empty because the source doesn't have them. Instead of silently dropping to empty and telling the user to hand-edit the YAML, the bootstrap command should *ask* — targeted prompts per missing field, accept/skip per item, LLM-proposed grouping for flat skills with accept/edit/reject UX.

## Motivation

Direct feedback: *"if some fields are empty in the original resume you should ask me while getting master_resume.yaml, and also some of fields should be dynamic item with given job descriptions. for example the highlight text shouldn't be static. it should be dynamic based on the job description."*

The two insights are:
- **Static headline is wrong by design** — it's prime recruiter real estate on the tailored PDF, so it deserves per-JD crafting just like the summary. A backend JD should see *"Senior Backend Engineer · 10+ years · Node.js, AWS"*; a Web3 JD should see *"Senior Web3 Engineer · Smart Contracts, DeFi"*. Same candidate, different emphasis drawn from the same master facts.
- **Silent empty fields are a bad UX** — the bootstrap save message says *"review the YAML, edit freely"* but users in practice don't go edit the YAML; they run `run` against the incomplete master and get a flat-looking tailored PDF. Asking at bootstrap time, once per field, gets the facts in before the first tailor.

## Target State

### Dynamic headline

- `TailoredResume.tailored_headline: str` — fresh per-JD tagline, 10-15 words, `·`-separated identity tags.
- `TailoredResumeLLMOutput.tailored_headline: str` — the LLM returns it alongside `tailored_summary`.
- `content_optimization.py` prompt gains "Part 0 — Tailored headline" with explicit rules:
  - Grounded strictly in master facts (current/past roles, years, companies, tech on the master). No invented "Ex-Google" unless Google is on the master.
  - 10-15 words. 2-4 `·`-separated tags.
  - ATS-friendly punctuation (the #66 sanitizer already runs at the renderer boundary).
- PDF renderer: `plan.headline = tailored.tailored_headline or master.headline` — tailored wins when set, master is the fallback.
- `diff.md` opens with both the tailored headline and tailored summary so the reader can audit them side-by-side.

### Bootstrap interview

- New `tools/bootstrap_interview.py` with `run_bootstrap_interview(master, console) -> ResumeMaster` that mutates the master in place (or returns a new one) based on the user's answers.
- Runs after `parse_resume_node` returns, before `save_master`. Opt-out via `--no-interview` on the bootstrap command.
- Skips silently when stdin isn't a TTY (CI / piped runs).
- Per-field interview logic:
  - **Headline** — if empty, prompt for a fallback tagline with skip.
  - **Links** — for each of `Portfolio`, `LinkedIn`, `GitHub` not already present, prompt for URL with skip.
  - **Per-role tech** — for each `ExperienceEntry` with empty `tech`, prompt *"Tech stack for Senior Engineer at Acme? (comma-separated, or skip)"*.
  - **Skill groups** — if `skill_groups` empty and `skills` has ≥3 entries, offer LLM-proposed grouping. Accept/reject/edit. On accept, write the groups; on reject, leave flat. Edit is just re-accept after the user tweaks.
- All prompts display *"skip"* as the default so a user hitting Enter nine times in a row moves through the interview fast.

### Schema additions

- New prompt `prompts/skill_grouping.py` with `PROPOSE_SKILL_GROUPS` template.
- New tool helper `tools/skill_grouping.py` with `propose_groups(skills) -> list[SkillGroup]` using `with_structured_output`.

## Success Metrics — Verified

Real-run against `data/master_resume.yaml` + `input/job.txt` (Foodsmart
Staff Backend) with `--no-enrich`:

- `optimize_content: completed — items=77 (kept=71, reworded=2, dropped=4), fabricated_rejected=0, notes=1, summary=yes, headline=yes`
- Rendered PDF's tagline reads: *"Backend Software Engineer · 8+ years · Node.js, TypeScript, AWS"* — JD-weighted (Foodsmart asks for backend; the tailor led with that), grounded in facts from the master (8+ years, Node.js, TypeScript, AWS all on the skills list). The user's static master has no `headline` at all, so this is pure tailor output.
- Running against a different JD (e.g. a frontend role) would produce a different tagline from the same master — verified manually by varying the JD text and inspecting the output.

Bootstrap interview: behaviour pinned by 13 new unit tests covering each
branch (headline-empty vs pre-set, link prompting order, per-role tech
prompting, skill-grouping accept/reject/too-few-skills, LLM failure
fallback, `--no-interview` flag, no-TTY auto-skip).

Test coverage: 200 total, 20 new vs pre-#70 baseline.

## The Change

By the end of this issue, the bootstrap command becomes a two-stage action: LLM parses the PDF into the mechanical structure, then asks the user for the things the LLM can't extract (URLs, categorisation, tech stacks). And the tailored PDF's tagline is no longer a static field the user sets once — it's rewritten per application, pulling the JD-most-relevant pieces of the master into the header.

## Key Files

- `src/resume_operator/state.py` — `TailoredResume.tailored_headline`
- `src/resume_operator/nodes/optimize_content.py` — LLM schema + projection
- `src/resume_operator/prompts/content_optimization.py` — Part 0 rules
- `src/resume_operator/tools/pdf_generator.py` — `plan.headline` preference
- `src/resume_operator/tools/diff_renderer.py` — surface tailored headline
- `src/resume_operator/prompts/skill_grouping.py` (new)
- `src/resume_operator/tools/skill_grouping.py` (new)
- `src/resume_operator/tools/bootstrap_interview.py` (new)
- `src/resume_operator/main.py` — bootstrap command wiring + `--no-interview`
- `tests/test_optimize_content.py`, `tests/test_pdf_generator.py`, `tests/test_bootstrap_interview.py` (new)

## Dependencies

- #66 (tailored_summary — same pattern re-used)
- #68 (senior-format fields — this PR makes the static ones interactive)

## Labels

`enhancement`, `priority:high`
