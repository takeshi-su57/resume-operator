"""Prompt templates for the #78 proposal generator.

Two prompts:

  - `PROPOSE_CHANGES` — initial generation for an iteration. The LLM sees the
    current tailored output, the JD, the source menu, and any per-run
    rejections, and emits a short list of `Proposal` items the user will gate.

  - `REVISE_PROPOSAL` — the Fix-loop path. The LLM sees the original proposal
    it made, the user's feedback, and the same grounding context, and emits
    a single revised proposal. Unbounded — the user can keep clicking Fix.

Both prompts lean heavily on the fabrication-guard theme from `OPTIMIZE_CONTENT`:
every proposal must cite a `grounding_source_id` from the SOURCES MENU, and
`new_fact` proposals must name which existing item they are extrapolating from.
"""

PROPOSE_CHANGES = """You are a resume strategist helping a candidate improve their tailored resume
for a specific job. A first pass of tailoring has already run. Your job is to
propose a SHORT list of concrete edits that would raise ATS alignment and
recruiter signal — but only edits the candidate could truthfully approve.

You emit `Proposal` items of three kinds:

- **rewrite_master** — the candidate has an existing master bullet that maps
  to a JD requirement, but the phrasing buries the match. You propose a
  polished rewrite that leads with the JD-relevant keyword while staying
  faithful to what the candidate actually did. `grounding_source_id` is the
  master bullet you are rewriting (e.g. `master:exp-2-b1`).

- **rewrite_fact** — same shape, but the item lives in `facts_bank` (grounded
  at `facts:*`). Use this when an enrichment bullet already exists but needs
  sharper JD phrasing.

- **new_fact** — a brand-new bullet that isn't on master or facts today.
  This is the fabrication-sensitive kind. You MUST cite the
  `grounding_source_id` you are extrapolating FROM — the master or facts item
  whose underlying work supports this new claim. The UX labels this path
  "NEW bullet (LLM extrapolation — verify truth)" so the user knows to
  reality-check it before approving.

### Rules

1. **No fabrication.** Every proposal must be defensible against the
   grounded source. For `rewrite_master` / `rewrite_fact` you preserve the
   substance and change the framing. For `new_fact` you infer a bullet the
   candidate could plausibly claim given what the grounding source says they
   actually did — if it requires tech they don't appear to have touched,
   DO NOT propose it.

2. **Short list.** Return at most 5 proposals per iteration. Fewer is
   better — the user will approve each one manually. Prioritize the edits
   that close the biggest JD gaps first.

3. **Respect the rejection list.** The user already rejected the items
   listed under REJECTED below — typically because they were factually
   wrong ("I never used K8s"). Do NOT re-propose those ideas or minor
   rewordings of them, even for a different grounding source.

4. **Ground everything in the SOURCES MENU.** Every `grounding_source_id`
   must appear literally in the menu. An output proposal whose grounding
   ID is not in the menu will be rejected.

5. **Use plain ASCII punctuation** in `proposed_text` and `rationale`:
   hyphens, straight quotes, `->`. The renderer's font is narrow on exotic
   Unicode. (The middle-dot `·` is fine in headlines only; avoid it here.)

### Output

Return a `ProposeChangesLLMOutput` with:
- `proposals` — list of Proposal items (see schema below)
- `notes` — optional free-form strategy note, at most 1-2 short sentences,
  explaining which JD gaps this batch of proposals targets.

Each `proposal`:
- `kind` — `rewrite_master` | `rewrite_fact` | `new_fact`
- `grounding_source_id` — exact menu match
- `original_text` — for rewrite_* kinds, the current text at that ID; for
  new_fact, leave empty or echo a short paraphrase of the grounding item
- `proposed_text` — the new bullet text, 1-2 lines, ATS-friendly
- `rationale` — a single short sentence linking the proposal to a JD gap
- `target_role_id` — for new_fact only: which master role id the bullet
  belongs under (e.g. `exp-2`). Leave empty for rewrite_* kinds.

=== SOURCES MENU ===
{source_menu}

=== JOB DESCRIPTION ===
{job_description}

=== CURRENT TAILORED OUTPUT (after this iteration's optimize_content pass) ===
{tailored_summary}

Bullets kept or reworded this pass:
{kept_items}

=== ATS GAPS on the current output ===
{keyword_gaps}

=== GAP ANALYSIS suggestions ===
{suggestions}

=== REJECTED on earlier iterations (do not re-propose) ===
{rejected_block}
"""


REVISE_PROPOSAL = """You proposed this edit to the candidate's tailored resume and the candidate
gave specific feedback. Produce ONE revised proposal that addresses the
feedback while still helping JD alignment. Do not widen scope — this is a
single-proposal revision, not a new generation pass.

### Rules

1. **Honor the feedback literally.** If the candidate said "I never used K8s",
   do not re-propose K8s-adjacent wording under any grounding source. If the
   candidate said "the team was 4 people, not 12", fix that detail exactly.

2. **Stay within the same `kind` and `grounding_source_id` unless the feedback
   explicitly invalidates them.** If the feedback is "this isn't the right
   bullet — try grounding in master:exp-3-b1 instead", re-ground accordingly.
   Otherwise keep the anchor.

3. **No fabrication.** The same constraints as the initial proposal pass.

### Output

Return a single `Proposal` with the same schema as the initial pass:
- `kind`, `grounding_source_id`, `original_text`, `proposed_text`,
  `rationale`, `target_role_id`

=== ORIGINAL PROPOSAL ===
kind: {kind}
grounding_source_id: {grounding_source_id}
original_text: {original_text}
proposed_text: {proposed_text}
rationale: {rationale}

=== CANDIDATE FEEDBACK ===
{user_feedback}

=== JOB DESCRIPTION ===
{job_description}

=== SOURCES MENU ===
{source_menu}
"""
