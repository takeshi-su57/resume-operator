# [Refactor]: Tighten OPTIMIZE_CONTENT — force aggressive drops when master doesn't match the JD

## Description

The tailor is keeping too much. On a real run against a Foodsmart backend JD with Bruno's master (Web3 / frontend-heavy), the optimizer kept 74 of 77 items and dropped 0. That means Web3 trading bots, Vue3 dashboards, and NFT contract work all survived in the tailored output — irrelevant to a backend-specific JD, and actively negative signal on the PDF.

Rewrite the `OPTIMIZE_CONTENT` prompt to push hard on drops, and add a post-run kept-ratio guard that warns (both in logs and in `diff.md`) when the tailor's decisions look too permissive.

## Motivation

Direct user feedback: *"and I noticed that you didn't optimize the resume for the job. what's up?"*

The current prompt just says *"decide keep / reword / drop"* and trusts the LLM. With `gpt-4o-mini` (and likely other conservative models), "keep" is the default — the model preserves anything that looks remotely related rather than committing to cuts.

A well-tailored resume for a Foodsmart backend JD should drop:
- Web3 smart-contract roles / NFT minting work
- Frontend-only bullets (Vue3 dashboards, Tailwind design systems)
- Older tech stacks the JD doesn't mention (Solidity, Ruby, PHP)
- Exploratory side-projects unrelated to backend web services

Keeping them isn't neutral — recruiters skim for focus, and a resume that mixes domains reads as unfocused. The tailor should be cutting, not preserving.

## Target State

### Prompt rewrite (`OPTIMIZE_CONTENT`)

Part 2 of the prompt gets explicit decision rules:

- **KEEP**: items directly supporting the JD's listed requirements (stack, responsibilities, domain)
- **REWORD**: items that support the JD but need a keyword or framing shift to make the match obvious
- **DROP**: items that don't advance this JD — different domain, different stack, frontend bullets in a backend JD, crypto/Web3 in a health-tech JD, etc.

Plus explicit target: "aim for a one-page resume, typically 4-8 bullets across 2-4 most recent roles". Plus a meta-check: "if you're keeping more than ~50% of the menu, re-evaluate — you're likely preserving items that don't advance this JD."

The fabrication guard and source-ID requirement stay unchanged.

### Kept-ratio guard in `optimize_content`

After validation, compute `kept_ratio = kept_or_reworded / index_size`. When it exceeds `0.7`:
- Log a warning: `optimize_content: kept-ratio 94% (74/79) — tailor may be under-optimizing`
- Append a structured note to `tailored.notes` so it surfaces in `diff.md` as a visible warning block

This doesn't block the run — the tailor still produces a PDF. It's feedback so the user knows when the tailor's decisions look permissive and might want to re-run, pick a different model, or accept that the master/JD are genuinely well-matched.

### diff.md surfacing

Notes that start with the `⚠` marker render in a dedicated "Warnings" callout at the top of `diff.md`, above the existing "Strategy Notes" block. So the user sees the warning at a glance when reviewing the diff.

## Success Metrics

- Re-running the Foodsmart tailor against Bruno's master drops the kept ratio materially from today's 94% (74/79). Target: under 70%. Verified end-to-end.
- When the tailor keeps > 70%, the user sees the warning in both the log and `diff.md`.
- When the tailor is well-matched (say kept ≤ 70%), no warning appears.
- No regressions on existing tests; 2-3 new tests cover the ratio guard.

## Key Files

- `src/resume_operator/prompts/content_optimization.py` — Part 2 rewrite
- `src/resume_operator/nodes/optimize_content.py` — kept-ratio guard + note
- `src/resume_operator/tools/diff_renderer.py` — "Warnings" block
- `tests/test_optimize_content.py` — guard threshold tests
- `tests/test_diff_renderer.py` (may need to create) — warning block rendering

## Dependencies

- #026 (OPTIMIZE_CONTENT prompt exists with fabrication guard)
- #66 (diff.md structure with strategy notes)

## Labels

`refactor`, `priority:high`
