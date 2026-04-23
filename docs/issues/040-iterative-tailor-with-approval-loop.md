# [Feature]: Iterative tailor loop with human-approved LLM suggestions, master read-only, overrides in facts_bank

## Description

Today the tailor is a single-pass filter. It reads `(master, facts, JD)`, produces a `TailoredResume` with keep/reword/drop decisions, renders the PDF — done. Two limitations Takeshi hit on real runs:

1. **The tailor can only subtract.** Even when `analyze_gaps` produces explicit "mention AWS Lambda" or "frame the Docker work as K8s-adjacent" suggestions, those never feed new items into the source menu — the gap analysis is informational, not generative. A master that's slightly off-domain for the JD can only shrink, not grow.
2. **There's no iteration driver.** One `ats_score` pass runs before optimization (the #44 skip gate); no pass runs after. If the tailored output scores 68%, the user manually re-runs, hand-edits master, re-runs — no feedback loop.

We already have the primitives: `analyze_gaps` writes suggestions, `ats_score` quantifies fit, and the enrich flow (#56) shows interactive human-in-the-loop over a structured proposal works. This issue wires them into one iterative loop.

## Motivation

Direct user observation on the current output: _"this system is just drop the items from the master and facts"_ — and the LLM's gap-analysis suggestions currently die on the floor. The natural flow when a JD asks for Kubernetes and the master only mentions Docker: LLM proposes a polished bullet framing the work → user approves (or rejects as fabrication) → next tailor iteration sees the approved bullet in the source menu → ATS score climbs → loop exits when the user is happy.

Three principles lock in:

1. **`master_resume.yaml` is read-only.** Every accepted change lands in `facts_bank.yaml`. Hand-authored master stays pristine — git blame and eyeballing the YAML always give the truth. The LLM never writes into master.
2. **Approval is three-button, not binary.** `Yes` (apply) / `No` (discard) / `Fix` (free-text feedback → LLM re-generates → back to the same three buttons on the revised version, unbounded). The Fix loop matters because the LLM's first draft is usually close but wrong on a detail ("I never used K8s, only ECS").
3. **Exit is user-driven, with a cap.** User decides when the ATS score is good enough. An iteration cap (default 3) prevents runaway token spend on unreachable scores, with an explicit _"continue anyway?"_ prompt at cap.

## Target State

### Graph shape

```
load_master
  → ats_score (initial)
  → [skip if ≥ skip_threshold, per #44]
  → iterate_tailor   ← new subgraph (see below)
  → generate_pdf
  → report_results

iterate_tailor subgraph:
  LOOP:
    analyze_gaps
    optimize_content      (tailor — produces TailoredResume)
    ats_score             (scores the tailored version)
    user_gate             "ATS={score}%. Accept this version?"
      YES → exit loop
      NO (and iter < cap) → continue
      iter >= cap → "Reached cap. Continue anyway?" YES resets counter; NO exits
    propose_changes       (new node — LLM emits Proposal[])
    approval_flow         (new CLI flow — three-button + Fix-loop)
    apply_approvals       (new node — writes to facts_bank.yaml)
    goto LOOP
```

The existing #44 skip-on-high-score path stays unchanged — a well-matched master never enters the loop.

### Proposal types

`propose_changes` emits `Proposal` items of three kinds. All three carry a `grounding_source_id` so the user can verify what it's anchored to.

| Kind             | What it does                                                   | UX label                                        |
| ---------------- | -------------------------------------------------------------- | ----------------------------------------------- |
| `rewrite_master` | Polishes an existing `master:exp-*-b*` bullet for JD alignment | "Rewrite of your existing master bullet"        |
| `rewrite_fact`   | Polishes an existing `facts:*` bullet                          | "Polish of a facts-bank entry"                  |
| `new_fact`       | Net-new bullet inferred from user's profile + JD gaps          | "NEW bullet (LLM extrapolation — verify truth)" |

`new_fact` is the fabrication-sensitive path. The prompt forces the LLM to cite which master/fact item it's extrapolating from ("extrapolating from `master:exp-2-b3` — you used Docker on a 50-service deploy; this reframes it as K8s-adjacent"), so the user has something to reality-check against when approving.

### Approval UX (interactive CLI, Rich-based)

For each proposal:

```
[proposal 1/7]  rewrite_master  (grounded in master:exp-2-b1)

  Original:  Led backend team building microservices
  Proposed:  Led backend team building Kubernetes-orchestrated
             microservices on AWS

  [Y]es   [N]o   [F]ix — give feedback, LLM revises
```

`Y` → proposal appended to facts_bank at end of run.
`N` → proposal recorded in `rejected_suggestions` (per-run memory, not persisted).
`F` → free-text prompt (_"I never used K8s, only ECS"_) → re-invoke `propose_changes` with `(original, proposed, user_feedback)` → emit revised Proposal → **back to the same three-button gate on v2, v3, ...** No cap on the Fix loop.

### Facts-bank schema: `overrides` field

```yaml
# facts_bank.yaml
bullets:
  - id: enrich-20260423-1
    text: "Led backend team building Kubernetes-orchestrated microservices on AWS"
    overrides: "master:exp-2-b1" # NEW optional field
```

`build_source_index` honors `overrides`: when a facts-bank entry declares an override on a master `source_id`, the original master entry is **hidden from the menu**. The tailor sees exactly one entry per thought — the override if present, the original otherwise. Zero duplication in the prompt or in the rendered PDF.

Delete the facts-bank entry → the master one resurfaces naturally. No cleanup bookkeeping.

### Rejection memory

`ResumeOptimizerState` carries `rejected_suggestions: list[RejectedSuggestion]` across loop iterations. Each entry: `(kind, grounding_source_id, rejected_text, user_reason_if_provided)`. The `propose_changes` prompt includes the current rejection list with "do not re-propose these items — the user already rejected them, here's why." Cleared at end of run — per-run context, not a permanent block.

### Iteration cap

Default `max_iterations = 3`, configurable via `--max-iter` (CLI) and `RESUME_MAX_ITERATIONS` (env). At cap:

```
Reached 3 iterations with ATS=76%. Continue iterating? [y/N]
```

`y` resets the counter and continues. `N` renders the PDF from the best-scoring iteration seen so far (not necessarily the current one).

### CLI

`run` gains two flags:

- `--max-iter N` — iteration cap (default 3)
- `--no-approve` — headless mode; skips the iteration loop entirely, behaves like today's single-pass tailor. Used for CI/batch.

## Success Metrics

- **Gap-bridging**: running against a master where the JD asks for Kubernetes but master only mentions Docker, the loop produces at least one accepted `rewrite_master` or `new_fact` bullet; ATS score climbs ≥ 5 points iteration-over-iteration until user accepts or cap reached.
- **Master invariant**: `master_resume.yaml` mtime is unchanged across any run. Any code path that mutates master is a bug.
- **Override persistence**: `facts_bank.yaml` overrides approved for JD A are available (and usable) for JD B's tailor without any manual step — the source_index honors them automatically.
- **Zero duplication**: when an override exists for `master:exp-2-b1`, the tailor's SOURCES MENU prompt contains exactly one entry covering that thought, not two.
- **Rejection honored**: when the user rejects a proposal with "I never used K8s", subsequent iterations in the same run do not re-propose K8s bullets with the same grounding source.
- **Cap prompt**: at iteration cap the user is prompted; choosing No produces a valid PDF from the best iteration seen.
- **Tests**: 6+ new tests covering (a) `propose_changes` grounds `new_fact` to a `source_id`, (b) `overrides` hides master entries from `build_source_index`, (c) rejection memory is passed into the proposal prompt, (d) Fix loop round-trips feedback back to the LLM, (e) iteration cap triggers the continue-anyway prompt, (f) `--no-approve` preserves today's single-pass behavior.

## Key Files

- `src/resume_operator/state.py` — add `Proposal`, `RejectedSuggestion`; extend `ResumeOptimizerState` with `proposals`, `rejected_suggestions`, `current_iteration`, `max_iterations`, `best_tailored_so_far`; add `overrides: str | None` to `FactsBankBullet`
- `src/resume_operator/graph.py` — assemble the `iterate_tailor` subgraph with conditional exit edges
- `src/resume_operator/nodes/propose_changes.py` (NEW) — LLM emits `Proposal[]` grounded in source_index + rejection memory
- `src/resume_operator/nodes/apply_approvals.py` (NEW) — persists approved proposals to `facts_bank.yaml` with correct `overrides` linkage
- `src/resume_operator/tools/approval_flow.py` (NEW) — three-button + Fix-loop CLI; reuses the Rich/Confirm/Prompt pattern from `tools/enrich.py`
- `src/resume_operator/tools/source_index.py` — honor the `overrides` field, hide shadowed master entries
- `src/resume_operator/tools/facts_bank.py` — schema bump; existing files without `overrides` default to `None`
- `src/resume_operator/prompts/propose_changes.py` (NEW) — two prompts: initial generation (with rejection list) and Fix-loop revision (with original + proposed + feedback)
- `src/resume_operator/main.py` — `--max-iter`, `--no-approve` flags
- `src/resume_operator/config.py` — `resume_max_iterations` setting
- `tests/test_propose_changes.py` (NEW)
- `tests/test_approval_flow.py` (NEW)
- `tests/test_source_index.py` — add overrides tests
- `docs/architecture.md` — document the loop + overrides mechanism

## Dependencies

- #39 aggressive-drop prompt (merged as PR #77) — the tailor is now crisp about dropping; this issue makes the companion additive path symmetric.
- #56 interactive enrich flow — `approval_flow.py` reuses its Rich-based Q&A pattern.
- #44 conditional-skip ATS routing — the initial-score skip stays unchanged; loop is entered only when the master isn't already a great match.

## Out of Scope

- **Persisting rejection memory across runs.** Per-run only. A rejection for JD A shouldn't silently suppress the same idea when tailoring for JD B next week.
- **Multi-JD batch mode.** Loop is single-JD; batching is future work.
- **ATS-score-driven auto-accept.** The user always decides whether to exit; the score is informational, not authoritative.

## Labels

`feature`, `priority:high`
