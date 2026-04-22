# [Refactor]: Collapse `enrich` into `run` as an auto-triggered inline step

## Description

After shipping the standalone `enrich` command in #62, real-world use revealed the CLI surface was too wide — users had to know when to bootstrap, when to run, when to enrich, and in what order. The enrichment prompt also didn't make it obvious that users should answer with *facts*, not *instructions* (first real session produced five "make it more professional" entries the user thought were transformation commands, not answers). Simplify to a single main entry point (`run`) that decides for itself when interview enrichment is needed, and tighten the interactive prompts so the facts-vs-instructions distinction is unmissable.

## Motivation

Direct quote from the bug report: *"currently the app is too complicated to use it"*. Three commands (`bootstrap`, `run`, `enrich`) for three steps is one command too many when the steps are sequential and can be chained. The user shouldn't have to diagnose that their tailored resume is thin and then remember that `enrich` is the follow-up — the main command should notice and offer the session itself.

## Target State

After this change:

1. **`resume-operator run --master M --facts F --job J`** is the one daily-use command.
2. Pipeline runs as before: load inputs → score → (skip or) analyze + optimize → generate PDF → report.
3. **Between optimize and generate_pdf**, if the tailoring is thin (`kept_or_reworded() < threshold`) AND stdin is a TTY AND `--no-enrich` wasn't passed, the CLI:
   - Pauses with a yellow panel explaining the situation
   - Asks "Start an enrichment session? [y/N]"
   - If yes: runs the interactive Q&A loop, appends accepted items to `facts_bank.yaml`, re-invokes the graph once to pick up the new facts
4. **The standalone `enrich` command is removed.** The interactive logic lives in `tools/enrich.py` where `run` calls it directly; nothing lost.
5. **The question-prompt UX is reworded** so the facts-vs-instructions distinction is explicit on screen. Example: before each input, print `Answer with facts and metrics (e.g. "I built 50+ endpoints serving 2M requests/day"). 'skip' skips; 'quit' ends.` followed by a bare `>` prompt.
6. New config: `enrich_threshold: int = 6` (min kept items before auto-enrich triggers) and `--no-enrich` flag on `run` for scripted / headless use.

## Success Metrics — Verified

- `resume-operator --help` lists 4 commands now (`run`, `parse-resume`, `bootstrap`, `score`) — the standalone `enrich` is gone. Confirmed via `python -m resume_operator enrich --help` returning *"No such command 'enrich'"*.
- Real-run against the bootstrapped master + `input/job.txt` with `--no-enrich`: pipeline completed cleanly (ATS 72%, 15 items kept, 3 reworded, 0 dropped). Auto-enrich would not have fired anyway — 15 ≥ 6 threshold — which is the correct decision for a rich-enough master.
- 154 tests pass (3 new + 4 retired). `TestRunAutoEnrich` covers all six trigger conditions for `_should_offer_enrich`: thin tailoring fires it, rich tailoring suppresses it, `--no-enrich` flag suppresses it, optimization-skipped state suppresses it, no-TTY suppresses it, and the legacy PDF path suppresses it.
- Improved prompt UX in `tools/enrich.run_interactive_session`: the panel header now reads *"For each question: answer with facts and metrics — e.g. \"I built 50+ endpoints serving 2M requests/day\" — not with instructions"*, and each question's input is preceded by a dim line *"Do NOT type instructions like 'make it professional' — that's the LLM's job in the polish step."*. This addresses the original failure mode where the user typed transformation directives instead of answers.

## The Change

By the end of this issue, the daily loop is: edit `master_resume.yaml` once, then for each new JD run `resume-operator run --master ... --job ...` — and the tool decides for itself whether to interview you for more material, never forcing a separate command or asking instruction-shaped questions.

## Key Files

- `src/resume_operator/main.py` — remove `enrich` command, add auto-enrich logic to `run`, improved question prompt UX
- `src/resume_operator/tools/enrich.py` — expose an interactive-session helper `run_interactive_session(...)` so `run` can call it
- `src/resume_operator/config.py` — `enrich_threshold` setting
- `tests/test_main.py` — delete `TestEnrichCommand`; add `TestRunCommand.test_auto_enrich_triggers_when_thin` + `test_respects_no_enrich_flag` + `test_does_not_trigger_when_full`
- `docs/architecture.md`, `README.md`, `.claude/CLAUDE.md` — simplified command table

## Dependencies

- #62 ✓ (enrich session logic exists to be reused)
- #60 ✓ (master preserves bullets — auto-enrich only makes sense once the master isn't a summary)

## Labels

`refactor`, `priority:high`
