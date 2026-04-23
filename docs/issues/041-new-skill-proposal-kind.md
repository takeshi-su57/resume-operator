# [Feature]: Add `new_skill` proposal kind — LLM recommends JD-relevant skills via the same approval loop

## Description

The #78 iterative approval loop added three proposal kinds — `rewrite_master`, `rewrite_fact`, `new_fact` — all of which target **bullets**. When a JD lists skills the master doesn't surface, the loop today can't do anything about it: the only paths that touch skills are the tailor's existing keep/drop decisions over master's `skills` / `skill_groups` / `facts.skills_beyond_master`, which can only **subtract**. There's no "the JD asks for Kubernetes and your master never mentions it — do you actually have it?" flow.

This issue adds a fourth kind, `new_skill`, that runs through the same Y/N/Fix three-button UX. Approved skills land in `facts_bank.skills_beyond_master`; rejections with reason go into the per-run `rejected_suggestions` list so the LLM doesn't re-propose the same skill next iteration.

## Motivation

Direct user observation, after running #78 against a Foodsmart backend JD:

> "currently we add experience bullet by LLM suggestion. but there is no skills recommend section. if the job requires some skills LLM should recommend me highly related skills to me."

External ATS reviews surface skill gaps as their most visible dimension (a side-by-side count table, JD-skill vs. resume-skill). Right now the loop can strengthen a bullet that mentions a skill, but it can't **add** the skill name itself into the skills section — so the ATS keyword scanner never sees the word. That's a solvable gap using the approval-loop machinery already in place.

## Target State

### Fourth proposal kind

`propose_changes` emits `Proposal(kind="new_skill", ...)` alongside the existing kinds. Shape is the same; behavior diverges in two places:

| Aspect | `new_fact` (bullet) | `new_skill` (new) |
|---|---|---|
| `grounding_source_id` | Master/facts item whose work supports the new bullet | Master experience item where the user *plausibly* used the claimed skill (e.g. `master:exp-2` because "microservices on Docker" is adjacent to Kubernetes) |
| `proposed_text` | Full bullet text, 1–2 lines | Bare skill name, e.g. `"Kubernetes"` |
| `original_text` | Usually empty | Always empty — skills don't have a pre-existing form |
| `target_role_id` | Role the bullet belongs under | Unused |
| UX label | "NEW bullet (LLM extrapolation — verify truth)" | "NEW skill (verify you actually have this)" |

The grounding requirement matters more for skills than for bullets: a polished bullet is tied to work you did; a claimed skill is a bare self-report. The prompt forces the LLM to cite which master experience item supports the claim, so the user has something concrete to reality-check against.

### Routing in `apply_approvals`

A new branch: when `proposal.kind == "new_skill"`, append the `proposed_text` to `facts_bank.skills_beyond_master` (deduping against existing entries), not `extra_bullets` / `projects`. No `overrides` linkage — skills are a flat string list, there's no master skill being shadowed by a facts skill.

### Prompt update

`PROPOSE_CHANGES` gets a short section for Part 2b: "When the JD lists skills not present on master/facts and the user plausibly has them given their experience, propose as `kind=new_skill` grounded in the master experience that supports the claim. Be conservative — only propose skills the grounding source genuinely implies the user has used."

The `rejected_suggestions` list already flows into the prompt, so a rejection like *"I never used K8s, only ECS"* teaches the LLM to stop proposing Kubernetes on subsequent iterations.

### Approval UX (minor)

`approval_flow._KIND_LABEL` gets a `new_skill` entry. No other flow changes — the three-button gate and Fix loop are kind-agnostic. The Fix loop for a skill has a narrower use case (*"I know Docker Swarm, not K8s — propose what I actually use"*) but still applies.

### Source index

`build_source_index` already emits `facts:skill:<name>` entries for skills in `facts.skills_beyond_master`. Once a `new_skill` is approved, the next iteration's tailor sees it in the SOURCES MENU under `facts:skill:<name>`, and `optimize_content` decides whether to keep/drop it against the JD — same as every other skill.

## Success Metrics

- Running against a master whose `skills` / `skill_groups` don't mention Kubernetes and a JD that does: the loop produces a `new_skill` proposal grounded in the closest relevant master experience.
- Approving a `new_skill` writes the name into `facts_bank.skills_beyond_master` (not `extra_bullets` / `projects`). Running again against a different JD that also asks for Kubernetes surfaces the approved skill in the tailored output without any re-approval.
- Rejecting a `new_skill` with reason "I never used X" prevents the LLM from re-proposing X on subsequent iterations of the same run.
- 3+ new tests cover: `new_skill` routed to `skills_beyond_master`, grounding fabrication guard still works, rejection memory honored for skills specifically.
- No regression in the existing bullet-proposal paths.

## Key Files

- `src/resume_operator/nodes/propose_changes.py` — accept `new_skill` as a valid kind; adjust `_infer_kind` fallback (today maps bare `master:skill:X` to `rewrite_master`, which is wrong — skills are rewritten as `rewrite_master` only when the user is polishing an existing master skill label).
- `src/resume_operator/prompts/propose_changes.py` — Part 2b section for skills, plus an example in the output schema block.
- `src/resume_operator/nodes/apply_approvals.py` — new branch: `proposal.kind == "new_skill"` → `bank.skills_beyond_master.append(proposed_text)` with dedupe.
- `src/resume_operator/tools/approval_flow.py` — `_KIND_LABEL["new_skill"]`.
- `tests/test_propose_changes.py`, `tests/test_apply_approvals.py`, `tests/test_approval_flow.py` — coverage for the new path.

## Dependencies

- **#78** (iterative approval loop) — must be merged first; this extends the same loop with a new kind. Should ship as its own PR on top of a merged #78.

## Out of Scope

- **`rewrite_skill`** — renaming/normalizing an existing skill ("TypeScript" vs "Typescript"). Skill names are usually exact-match keywords; the tailor's keep/drop decisions already handle this path. Not worth its own kind.
- **Skill-group assignment** — once a new skill lands in `skills_beyond_master`, the user can manually move it into a `skill_groups` category on master. Auto-categorization is a separate (optional) follow-up.

## Labels

`enhancement`, `priority:medium`
