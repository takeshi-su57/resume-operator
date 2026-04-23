# How to use: iterative tailor with approval

This is the default `run` experience (#78). Each tailored version is scored against the JD, you accept it or ask the LLM to propose improvements, and accepted improvements grow `facts_bank.yaml` so future runs start from a better baseline.

For the pipeline architecture and graph shape, see [docs/architecture.md](../architecture.md).

## What this feature does

Before #78, `run` was a one-shot filter: given `(master, facts, JD)`, it produced a tailored PDF and stopped. If you weren't happy, your only options were to hand-edit the master and re-run, or accept a resume that didn't fully bridge the JD's gaps.

With the approval loop, the LLM can now **propose edits** — polishing existing bullets, extrapolating new ones from your real experience — and you gate each one with three buttons (Yes / No / Fix). Accepted proposals land in `facts_bank.yaml` with a schema that keeps `master_resume.yaml` hand-authored and untouched. On the next JD, your approved bullets are already there.

## Prerequisites

- The standard setup from [docs/guides/development.md](development.md) — Python 3.12, `uv sync --dev`, an LLM API key in `.env`.
- A `data/master_resume.yaml` (run `bootstrap` once from an existing PDF if you don't have one).
- A job description saved as `job.txt` (or any path you'll pass to `--job`).
- **A real TTY** — the loop is interactive. Headless shells / CI auto-skip it (see [Headless mode](#headless-mode) below).

## A first-run walkthrough

```bash
uv run python -m resume_operator run \
  --master data/master_resume.yaml \
  --facts data/facts_bank.yaml \
  --job input/job.txt
```

### Step 1 — Initial tailor pass

The pipeline runs `load_master → ats_score → analyze_gaps → optimize_content → ats_score_tailored`. When it lands, you see:

```
Iteration 1/3: ATS score on tailored output = 73%
Accept this tailored version and generate the PDF? [y/N]:
```

**If 73% is good enough for you, press `y`** — the loop exits, `generate_pdf` and `report_results` run once, and you get `resume.pdf` + `diff.md` + `tailored.yaml` in a per-application folder like `data/applications/2026-04-23_foodsmart/`. Done.

**If you want to push the score higher, press `n`** (the default). The loop moves to step 2.

### Step 2 — LLM proposes edits

You see a spinner (`LLM proposing tailored edits...`) while `propose_changes` runs. The LLM sees the current tailored output, the JD's remaining keyword gaps, the master/facts source menu, and any rejections from earlier iterations (on run 1 that list is empty). It emits up to 5 grounded proposals.

### Step 3 — You gate each proposal with three buttons

For each proposal, a panel appears:

```
╭─ Proposal 1/4 ─────────────────────────────────────────────╮
│ Rewrite of your existing master bullet                     │
│ grounded in master:exp-2-b1                                │
│                                                             │
│ Original:  Led backend team building microservices          │
│ Proposed: Led backend team building Kubernetes-orchestrated │
│           microservices on AWS, deploying via GitHub        │
│           Actions CI/CD                                     │
│                                                             │
│ Why: Surfaces the K8s + CI/CD keywords the JD asks for      │
╰─────────────────────────────────────────────────────────────╯
[Y]es / [N]o / [F]ix — give feedback, LLM revises / [q]uit:
```

Three options:

- **`y`** — accept. The proposal will be written to `facts_bank.yaml` at the end of this iteration.
- **`n`** — decline. You get an optional prompt: *"Why not?"* — anything you type here is fed back into the next iteration's proposal generation so the LLM avoids the same idea. A useful reason like *"I never used K8s, only ECS"* teaches the model in a way a silent `n` doesn't.
- **`f`** — fix. You type free-text feedback; the LLM produces a revised version (`v2`); you see the same three-button panel on `v2`. You can keep clicking Fix as many times as you want — unbounded.
- **`q`** — quit the approval step entirely. The loop returns the best-scoring iteration you've seen.

### Step 4 — Facts-bank grows, loop re-runs

After you've gated all proposals (or quit mid-way), `apply_approvals` writes accepted proposals to `facts_bank.yaml`:

- `rewrite_master` → new `extra_bullets` entry with `overrides: "master:exp-2-b1"`.
- `rewrite_fact` → existing facts entry's text replaced in place (same id).
- `new_fact` → new entry in `extra_bullets` (if the LLM named a target role) or `projects` (otherwise).

The loop re-invokes the tailor graph. `load_master` re-reads both files from disk, so the updated facts are automatically picked up. `build_source_index` hides any master entry that a facts entry overrides — the next tailor pass sees **one entry per thought**, no duplication.

Then iteration 2 starts: fresh ATS score, fresh user gate. Repeat until you accept, the LLM runs out of proposals, or the cap fires.

## The three proposal kinds

Every proposal carries a `grounding_source_id` so you have an anchor to verify against.

| Kind | What it does | Groundings | Reality-check |
|---|---|---|---|
| `rewrite_master` | Polishes an existing master bullet for JD alignment | `master:exp-*-b*` (bullets), `master:exp-*` (role headers), `master:skill:*`, etc. | Does the polish still describe what you actually did? If yes, accept. |
| `rewrite_fact` | Polishes an existing `facts:*` entry | `facts:enrich-*`, `facts:approved-*`, etc. | Same check — polish without drift from reality. |
| `new_fact` | Brand-new bullet extrapolated from an existing source | Cites which master/facts item the new claim is **extrapolated from** | Does the grounded source actually support this claim? This is the fabrication-sensitive path — be strict. |

**For `new_fact` especially**: the LLM is required to tell you *"extrapolating from `master:exp-2-b3` — you used Docker on a 50-service deploy; this reframes it as K8s-adjacent."* Your job is to verify the grounding is real. If the grounded bullet doesn't actually support the proposed claim (you did Docker but never K8s, say), hit `n` with a reason. If it does support it but the wording is off, hit `f` to fix.

## The `overrides` mechanism (why master stays pristine)

`master_resume.yaml` is **strictly read-only**. Every accepted LLM edit lands in `facts_bank.yaml`. When a `rewrite_master` is approved, the new facts entry carries an `overrides` field:

```yaml
# data/facts_bank.yaml
extra_bullets:
  - id: approved-20260423-1
    text: "Led backend team building Kubernetes-orchestrated microservices on AWS"
    role_id: exp-2
    overrides: "master:exp-2-b1"     # ← points at the shadowed master bullet
    source: "approved 2026-04-23"
```

On the next `build_source_index` call, the original `master:exp-2-b1` is hidden from the menu. The tailor sees only the polished override. Zero duplication in the prompt, zero duplication in the rendered PDF.

**Why this matters**:

- You can always trust `master_resume.yaml` — if it's in there, you typed it.
- `git blame` + eyeballing the YAML give you the truth without LLM interference.
- Deleting an approved facts entry makes the original master bullet resurface naturally — no cleanup bookkeeping.
- An override approved for JD A is automatically available for JD B's tailor on the next run.

## The iteration cap

The default cap is 3 iterations. When iteration 3 ends with a reject, you see:

```
Reached 3 iterations (best ATS=78%). Continue iterating?
Continue anyway? [y/N]:
```

- **`n`** — render the **best-scoring iteration** seen so far (not necessarily the current one). Useful when iteration 3 regressed and iteration 2 was actually better.
- **`y`** — add another cap on top and keep going.

Override the default with `--max-iter N` or set `RESUME_MAX_ITERATIONS` in `.env`.

## Headless mode

Set `--no-approve` on the CLI (or run from a non-TTY shell) to skip the loop entirely. You get today's single-pass behavior: one tailor, render the PDF, done. Useful for CI, batch, and scripted runs.

```bash
uv run python -m resume_operator run \
  --master data/master_resume.yaml \
  --job job.txt \
  --no-approve
```

`--no-enrich` is the equivalent opt-out for the upstream enrich interview (which can still fire before the approval loop when the first tailor pass is thin). Pass both for a fully non-interactive run.

## Tips

### Give specific Fix feedback

The LLM can't guess what's wrong with a proposal from a silent `n`. Useful feedback patterns:

- **Factual corrections**: *"The team was 4 people, not 12. We ran on ECS, not K8s. That project was internal, not customer-facing."*
- **Tone**: *"Less buzz-wordy — 'orchestrated microservices' sounds bloated. Keep it plain."*
- **Keyword alignment**: *"Lead with 'PostgreSQL' instead of 'SQL databases' — the JD uses Postgres specifically."*
- **Scope**: *"This belongs on exp-3, not exp-2. Re-ground it there."*

### When to use Fix vs. No

- **Fix** when the *direction* is right but details are wrong ("yes polish this, but not with these exact words").
- **No** when the *direction* is wrong ("don't propose anything around this topic — I never did that work").

A rejection with a reason teaches the LLM to avoid the whole idea next iteration. A Fix keeps the conversation on that specific proposal.

### Watch for regressions

The best-so-far guard exists for a reason: sometimes iteration 2 pulls harder on a JD keyword at the cost of the overall coherence and the score drops. The loop silently tracks this — if you hit the cap and decline, you get the *best* iteration, not the *current* one. Useful when you realize mid-run that you've overshot.

### `facts_bank.yaml` is your memoized polish

Every run grows it. An override approved for a Foodsmart backend JD is there when you tailor for a different backend JD next week — no re-approval needed, no re-LLM-call needed for that specific bullet. The tailor just picks it up from the source menu.

Over time, `facts_bank.yaml` becomes a library of JD-polished versions of your experience. You can also hand-edit it freely; the `overrides` field is just a string pointing at a `master:*` source_id, so you can craft overrides manually without the LLM in the loop.

## What you get at the end

Every `run` (with or without the loop) produces a per-application folder:

```
data/applications/2026-04-23_foodsmart/
├── resume.pdf       ← tailored, rendered
├── results.json     ← ATS score, gap analysis, timing
├── tailored.yaml    ← the TailoredResume object (inspectable)
└── diff.md          ← human-readable keep/reword/drop breakdown
```

`diff.md` is the one to check when something feels off — it shows exactly which master/facts items were kept, which got reworded (with before/after), which were dropped, and any warnings from the tailor (e.g. "kept-ratio above 70%, may be under-optimizing" from #39).

## CLI reference

```bash
uv run python -m resume_operator run \
  --master data/master_resume.yaml \    # required (or --resume for the legacy PDF path)
  --facts data/facts_bank.yaml \        # optional; auto-loaded if the default path exists
  --job input/job.txt \                 # required
  --style input/style.consolas.yaml \   # optional StyleTemplate override
  --max-iter 5 \                        # optional cap (default 3; also RESUME_MAX_ITERATIONS)
  --no-approve \                        # optional: skip the #78 loop entirely
  --no-enrich \                         # optional: skip the upstream enrich interview
  --verbose                             # optional: DEBUG logging
```

Related env vars (see `.env.example`):

- `RESUME_MAX_ITERATIONS=3` — default cap
- `ATS_SKIP_THRESHOLD=0.9` — if the initial master-vs-JD score is at or above this, optimization is skipped entirely and the loop never enters
- `RESUME_STYLE_PATH=` — default StyleTemplate path (overridden by `--style`)
