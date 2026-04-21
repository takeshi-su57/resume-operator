# [Feature]: Add `facts_bank.yaml` for items beyond the master resume

## Description

A second source-of-truth YAML for projects, metrics, achievements, extra bullets, and skills that didn't fit on the trimmed master resume. During tailoring, the optimizer can pull items from the facts bank into the output when they're a strong match for the JD.

## Motivation

A paper resume only fits N items. Any specific JD may need items not on the current master. Without a facts bank, the tailor can only reorder or rephrase what's already on the master — it can't *add back* a relevant project. That forces the user to manually edit the master per application, which is the friction this plan exists to eliminate.

The plan doc calls this out explicitly ([plan 002, Key details](../../../../luckyplans/plans/002-resume-ats-tailor/plan.md)).

## Implementation

- [x] `FactItem` (with optional `role_id` for spliceable bullets) and `FactsBank` Pydantic models in [state.py](../../src/resume_operator/state.py)
- [x] `facts_path` and `facts: FactsBank` added to `ResumeOptimizerState`
- [x] [`tools/facts_bank.py`](../../src/resume_operator/tools/facts_bank.py) with `load_facts(path)` — returns an empty bank on missing/null path (optional by design), raises only on malformed YAML
- [x] `load_master` node now also loads the optional facts bank (same node since it's the "ingest structured inputs" step)
- [x] `optimize_content` prompt updated ([content_optimization.py](../../src/resume_operator/prompts/content_optimization.py)) — facts are a distinct section the LLM may pull from, with explicit instruction never to invent items
- [x] `optimize_content` node passes `state.facts` to the prompt
- [x] `run` CLI accepts `--facts` (optional); auto-falls-back to `data/facts_bank.yaml` if it exists
- [x] [`input/facts_bank.example.yaml`](../../input/facts_bank.example.yaml) added
- [x] Docs updated: `docs/architecture.md`, `README.md`

## Acceptance Criteria — Verified

- `run --master m.yaml --facts f.yaml --job j.txt` loads both without error (verified end-to-end against OpenRouter)
- Missing facts bank is not an error — optimizer runs master-only (covered by unit test + real run without `--facts`)
- Optimizer prompt receives facts as a distinct JSON block (not merged into the resume)
- Real-run proof: LLM's `changes_made` explicitly cited `proj-1`, `proj-2`, `extra-1`, and AWS skills from the facts bank in the tailored output — "Incorporated metrics pipeline project (proj-1) and Lambda migration project (proj-2)…", "Inserted GitHub Actions adoption bullet (extra-1)…"

## Key Files

- `src/resume_operator/state.py`
- `src/resume_operator/tools/facts_bank.py` (new)
- `src/resume_operator/nodes/load_master.py`
- `src/resume_operator/nodes/optimize_content.py`
- `src/resume_operator/prompts/content_optimization.py`
- `src/resume_operator/main.py`
- `input/facts_bank.example.yaml` (new)

## Follow-ups

- #026 will structure the facts-used tracking into `TailoredResume.source_id` so `diff.md` can show *which* fact was pulled and from where, instead of relying on the LLM's free-form `changes_made` narration.

## Dependencies

- #024 ✓

## Labels

`enhancement`, `priority:high`
