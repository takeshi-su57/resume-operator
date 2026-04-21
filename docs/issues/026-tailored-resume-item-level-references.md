# [Refactor]: Restructure `OptimizedResume` → `TailoredResume` with item-level references

## Description

Replace `OptimizedResume.sections: dict[str, str]` (blob per section) with `TailoredResume` — a list of `TailoredItem` objects that reference master/facts items by stable ID with per-item action (keep / reword / drop). This enables a real diff and makes fabrication structurally hard.

## Motivation

The previous `optimize_content` node had the LLM write free-form text blobs per section. Problems:

1. **No real diff.** `changes_made: list[str]` was free-form LLM narration, not a diff.
2. **Weak fabrication guardrail.** The prompt said "do not fabricate" — that was all. No structural check.
3. **PDF renderer lost structure.** Paragraph splitting on LLM whitespace (`pdf_generator.py`).

With item-level references, the LLM's job shrinks from "rewrite the resume" to "for each master/facts item: keep, drop, or reword." Fabrication requires the source item to exist first — the node rejects any `source_id` not in the `SourceIndex`.

## Implementation

- [x] `TailoredItem` (source_id, action, original_text, new_text) and `TailoredResume` (items + notes) added to [state.py](../../src/resume_operator/state.py)
- [x] `state.tailored_resume` field added to `ResumeOptimizerState` (kept alongside legacy `optimized_resume` for back-compat until #027 lands)
- [x] [`tools/source_index.py`](../../src/resume_operator/tools/source_index.py) — builds a `SourceIndex` from master + facts, with `source_id` format like `master:exp-1-b1`, `facts:proj-1`, `master:skill:Python`, etc. Provides `as_prompt_menu()` for the prompt and `__contains__` for the fabrication guard.
- [x] [`prompts/content_optimization.py`](../../src/resume_operator/prompts/content_optimization.py) rewritten — gives the LLM an explicit sources menu, asks for per-item keep/reword/drop decisions
- [x] [`nodes/optimize_content.py`](../../src/resume_operator/nodes/optimize_content.py) rewritten — uses `TailoredResumeLLMOutput` schema via `with_structured_output` (#028), validates every `source_id` against the index, records rejected IDs in `state.errors`
- [x] Legacy `OptimizedResume.sections` projection retained for back-compat — built from `TailoredResume` grouped by kind (summary/experience/skills/education). `generate_pdf` still reads this until #027 migrates it off the blob shape.
- [x] [`tools/diff_renderer.py`](../../src/resume_operator/tools/diff_renderer.py) — renders `diff.md` with Strategy Notes, Additions (facts pulled in), Rewordings (before/after), Deletions
- [x] [`nodes/report_results.py`](../../src/resume_operator/nodes/report_results.py) — writes `data/diff.md` whenever `tailored_resume.items` is populated
- [x] [`nodes/parse_resume.py`](../../src/resume_operator/nodes/parse_resume.py) now also synthesizes a `ResumeMaster` (via `resume_data_to_master`) so the legacy PDF path still has a source index
- [x] `conftest.py` fixtures updated — `sample_master` with stable IDs

## Acceptance Criteria — Verified

- No free-form section blobs in the pipeline's authoritative output — the `TailoredResume.items` list is the source of truth; `OptimizedResume.sections` is a derived projection for back-compat only ✓
- `optimize_content` produces only items traceable to master or facts ✓ (test `test_rejects_fabricated_source_id` covers the path; real-run showed `fabricated_rejected=0` because the LLM respected the menu)
- `diff.md` shows additions, deletions, and rewords with before/after text ✓ (see proof below)
- An LLM response referencing a non-existent `source_id` is caught and logged in `state.errors` ✓

## Proof of Work

Real-run against OpenRouter + `openai/gpt-4o-mini` with `master_resume.example.yaml` + `facts_bank.example.yaml` + `job.txt`:

```
optimize_content: completed — items=27 (kept=21, reworded=1, dropped=5), fabricated_rejected=0, notes=1
report_results: completed — wrote data/results.json and data/diff.md
```

Excerpt from the generated `diff.md`:

```markdown
## Additions — items pulled from the facts bank
- **facts:proj-2** (project) Led migration of 20+ Lambda functions from Node.js 14 → 18…
- **facts:extra-1** (extra-bullet[exp-1]) Drove adoption of GitHub Actions across the org…
- **facts:skill:Docker** (skill) Docker

## Rewordings — master or facts items with adjusted phrasing
- **master:exp-2-b2** (experience-bullet)
  - before: Introduced end-to-end Playwright tests, reducing regression bugs 60%.
  - after:  Implemented comprehensive testing practices, significantly decreasing regression bugs by 60%.
```

## Key Files

- `src/resume_operator/state.py`
- `src/resume_operator/nodes/optimize_content.py`
- `src/resume_operator/nodes/report_results.py`
- `src/resume_operator/nodes/parse_resume.py`
- `src/resume_operator/prompts/content_optimization.py`
- `src/resume_operator/tools/source_index.py` (new)
- `src/resume_operator/tools/diff_renderer.py` (new)
- `docs/architecture.md`
- `tests/conftest.py`, `tests/test_optimize_content.py`, `tests/test_report_results.py`, `tests/test_integration.py`

## Follow-ups

- #027 migrates `generate_pdf` off the back-compat `OptimizedResume.sections` projection and onto structured rendering from `TailoredResume + ResumeMaster` directly.
- #029 writes `diff.md` into a per-application folder instead of the single `data/diff.md`.

## Dependencies

- #024 ✓
- #028 ✓ (structured output makes the per-item schema clean)

## Labels

`refactor`, `priority:high`
