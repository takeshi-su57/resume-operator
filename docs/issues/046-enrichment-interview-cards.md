# [Feature]: Enrichment interview screen with Q→answer→polish card stack — Phase 4 of desktop GUI

GitHub issue: [#87](https://github.com/takeshi-su57/resume-operator/issues/87) · PR [#93](https://github.com/takeshi-su57/resume-operator/pull/93)

## Description

The auto-enrichment session (#033, inlined into `run` in #034) triggers when the first tailor pass comes back thin. The LLM proposes up to 5 grounded questions, the user answers in free text, and accepted items land in `facts_bank.yaml`. Today that whole exchange runs through `rich.prompt.Prompt.ask` in a scrolling terminal. This issue ports it to a dense, keyboard-driven card stack that matches the Linear-style aesthetic of the rest of the desktop GUI.

## Motivation

Enrichment is the tool's best feature for growing a thin master, but the terminal flow buries the bucket classification (project / extra_bullet / skill / certification) and the role linkage. The card UI surfaces those decisions explicitly so the user can see what's happening without reading the CLI logs.

## Target State

Replaces the placeholder pane that Phase 3 left for the `enrich_question` and `enrich_polished` session phases with proper components, and wires the `e` (edit) → `text` two-step that `tools.enrich.run_interactive_session` runs server-side.

### EnrichQuestionPane

```
┌─────────────────────────────────────────────┐
│ ENRICHMENT · QUESTION 2 / 5    [role:exp-1] │
│                                             │
│ At TechCorp, what was the scale of the      │
│ backend system you shipped?                 │
│ why: JD emphasizes scalable backend work.   │
│                                             │
│ Answer with facts and metrics — e.g.        │
│ "I built 50+ endpoints serving 2M req/day". │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ > I built REST endpoints… ▍             │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [Polish →  Ctrl+⏎]  [Skip]            [Quit]│
└─────────────────────────────────────────────┘
```

Auto-focuses the textarea on each new question. Skip and Quit send the literal `"skip"` and `"quit"` strings the server's `run_interactive_session` short-circuits on.

### EnrichPolishedPane

```
┌─────────────────────────────────────────────┐
│ ENRICHMENT · POLISHED 2 / 5                 │
│ q: At TechCorp, what was the scale…         │
│                                             │
│ [extra bullet]  [role: exp-1]               │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ Designed RESTful API for 50+ endpoints  │ │
│ │ at TechCorp, cutting p99 latency 30%    │ │
│ │ via Redis caching.                      │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [Accept a] [Edit e] [Reject r] [Skip s][Quit│
└─────────────────────────────────────────────┘
```

Bucket gets a tinted badge so the user can see at a glance whether the polish landed as a project / extra_bullet (with role_id chip) / skill / certification — same classification the CLI prints in magenta.

### The edit two-step

Server-side, picking `e` triggers a follow-up text prompt for the new wording. Two messages, one user intent. The workspace handles it like this:

1. User clicks **Edit** on the polished pane → component locally expands a textarea pre-filled with the polished text. *No server traffic yet.*
2. User types the correction; clicks **Save edit** → `onEnrichEditSubmit(draft)` fires.
3. `workspace.tsx` stashes the draft in a `pendingEnrichEditRef` and sends `e` via `controller.editEnrich()`.
4. Server receives `e`, fires the "Your wording" text prompt, controller routes it to the `enrich_edit` role.
5. The `useEffect` watching `pendingPrompt` notices the matching role and flushes the stashed draft via `controller.sendText`.

From the user's perspective: type, save, done — invisible round-trip.

Cancel during edit just collapses the textarea without sending anything; the server is still blocked on the `choose` prompt so the user can pick a/r/s/q normally.

### Keyboard model

Phase 3's keyboard handler in `workspace.tsx` already gated `Enter`/`x`/`f`/`q` for the approval pane. This phase adds the `enrich_polished` shortcuts (`a` / `r` / `s` / `q`) on the same global handler. Edit (`e`) is button-only because the keystroke would conflict with typing once the textarea expands.

## Success Metrics

- A full enrichment session against `data/master_resume.yaml` with a thin JD produces the same `facts_bank.yaml` writes as the CLI.
- LLM polish step round-trips visually (spinner → card flip).
- Every CLI keypress (`a` / `e` / `r` / `s` / `q`) has a keyboard equivalent.
- Skipping a question doesn't consume the polish LLM call — same short-circuit as the CLI.
- Auto-trigger threshold (`ENRICH_THRESHOLD` from `config.py`) honored.

## Key Files

- `desktop/src/screens/run/enrich-question-pane.tsx` (NEW).
- `desktop/src/screens/run/enrich-polished-pane.tsx` (NEW).
- `desktop/src/screens/run/workspace.tsx` — replace placeholder pane with the new components, add the deferred enrich-edit reply effect.
- `desktop/src/screens/run/use-run-controller.ts` — already wires `acceptEnrich` / `editEnrich` / `rejectEnrich` / `skipEnrich` / `quitEnrich` from Phase 3; no changes needed.

## Dependencies

- **#045** (Phase 3) — reuses the WS plumbing, the controller, and the workspace shell.

## Out of Scope

- Standalone "manual enrichment" entry point — Phase 4 only triggers from inside `run`.
- Bulk-enrichment tooling (multiple JDs at once) — single-session only.

## Labels

`enhancement`, `priority:high`
