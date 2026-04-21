# [Refactor]: Preserve every resume bullet on bootstrap (no summarization)

## Description

When `bootstrap` parses a PDF into `master_resume.yaml` today, the LLM collapses each role's bullets into a single dense summary sentence. That defeats the point of the master YAML: downstream tailoring (#026) has nothing to keep/reword/drop at bullet granularity, the rendered PDF looks sparse, and any prior hand-editing effort on the PDF is lost on every re-bootstrap.

Change the PARSE_RESUME prompt and the LLM output schema so every bullet is preserved verbatim. Also trim `bootstrap` to only run `parse_resume` — today it accidentally invokes the full graph and burns three extra LLM calls on ats_score / analyze_gaps / optimize_content the user never asked for.

## Motivation

Verified end-to-end against a real resume — 13 roles came out as 13 single-bullet entries, the tailor had no meaningful per-role choices to make, and the tailored PDF rendered with 4 sparse bullets. Rebuilt masters lose whatever bullet structure existed on the source PDF.

## Target State

After this change:

1. `ResumeExperienceLLM` exposes `bullets: list[str]` instead of the old `description: str`. The LLM fills a real list; no string-joining-with-newlines coincidence carries the data.
2. `PARSE_RESUME` prompt explicitly instructs: preserve every bullet verbatim; do not summarize; if the source has four bullets, the output has four items in `bullets`; do not invent bullets; do not truncate.
3. `parse_resume` node converts each LLM experience entry into a `ResumeData.experience` dict with `description` set to `"\n".join(f"- {b}" for b in bullets)`, so the existing `resume_data_to_master` conversion still works (it already splits multi-line descriptions on newlines — see `tools/master_resume.py:_parse_bullets`).
4. `bootstrap` CLI runs only the `parse_resume` node, not the full graph — no unnecessary ats_score / analyze_gaps / optimize_content / generate_pdf / report_results calls during ingestion.

## Success Metrics — Verified

Real-run against `input/resume.pdf` (Takeshi Suzuki's actual resume) with
`LLM_MODEL=openai/gpt-4o-mini`:

- Before this PR: 13 roles × 1 summary bullet each = 13 total bullets.
- After this PR: 13 roles, most with 3-4 bullets each = ~40 bullets.
  Example — `exp-2` (Lead Software Engineer @ UrbanMix.Tech) now has 4 bullets:
  "Built a real estate project management…", "Led and managed an agile team…",
  "Utilized Terraform to automate configuration…", "Enhanced D3 model
  rendering…" — exactly what appears on the source PDF.
- `bootstrap` logs show only a single `parse_resume` call. No ats_score /
  analyze_gaps / optimize_content / generate_pdf / report_results noise.
- A subsequent `run` against this richer master produced a tailored PDF with
  real backend-relevant material (AWS + CI/CD + Docker at Biblionexus,
  RESTful APIs at TechGropse, Kotlin native integration at Hilolabs) and the
  fabrication guard from #026 caught two hallucinated skills
  (`master:skill:AWS`, `master:skill:SQL`) — validation working on real
  content, not just the example YAMLs.

## The Change

By the end of this issue, `bootstrap` extracts structured content *as it is* on the source PDF, and `master_resume.yaml` becomes the rich source of truth #024 promised — not a compressed summary.

## Key Files

- `src/resume_operator/prompts/resume_parsing.py` — new prompt body
- `src/resume_operator/nodes/parse_resume.py` — `ResumeExperienceLLM.bullets: list[str]`, join to `description` when writing `ResumeData`
- `src/resume_operator/main.py` — `bootstrap` calls `parse_resume` directly
- `tests/test_parse_resume.py`, `tests/test_integration.py` — fixtures updated to use `bullets: [...]`

## Dependencies

- #024 ✓ (bootstrap exists)
- #028 ✓ (structured output — the schema change lives in the LLM output class)

## Labels

`refactor`, `priority:medium`
