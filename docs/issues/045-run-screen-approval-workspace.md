# [Feature]: Three-pane Run screen with live node timeline and approval workspace — Phase 3 of desktop GUI

GitHub issue: [#86](https://github.com/takeshi-su57/resume-operator/issues/86) · PR [#92](https://github.com/takeshi-su57/resume-operator/pull/92)

## Description

The crown-jewel screen of the desktop GUI roadmap. The iterative approval loop (#040) today is a scrolling terminal prompt: user sees a cyan `Panel` with an original/proposed pair and types `y`/`n`/`f`. There's no diff view, the ATS breakdown lives screens away, node progression is invisible, and the Fix loop makes you lose the thread. This issue turns it into a **three-pane side-by-side workspace** where every decision has full context on screen at once.

## Motivation

This is the screen that justifies the whole desktop GUI effort. The other phases are plumbing or coverage; this is where the user gets visible value over the CLI.

## Target State — three-pane Run workspace

```
┌──────────────┬───────────────────────────────────┬───────────────────┐
│ NODE TIMELINE│ CURRENT PROPOSAL  1/5  [rewrite]  │ ATS BREAKDOWN     │
│              │                                   │                   │
│ ◉ load_master│ work.2.bullets.0                  │ composite  78%    │
│ ◉ ats_score  │                                   │ ─────────────     │
│ ◉ analyze    │ - Built scalable API              │ hard skills  84%  │
│ ◉ optimize   │   infrastructure                  │ soft skills  72%  │
│ ◎ ats_tailor │ + Scaled Go API to 10k req/s     │ structural   90%  │
│ ○ approve ←  │   with Redis caching, cut         │ title match  60%  │
│ ○ finalize   │   p99 latency by 40%              │ measurable   88%  │
│              │                                   │ tone         75%  │
│ iter 1  64%  │ rationale: JD emphasizes scale…   │                   │
│ iter 2  78%  │ source: master:exp-2-b3           │ KEYWORD GAPS      │
│              │ confidence: 0.86                  │ • kubernetes      │
│              │                                   │ • terraform       │
│              │ [⏎] accept  [x] reject  [f] fix   │ • grpc            │
│              │                                   │                   │
│              │ 1/5 ──●────────  4 remaining      │                   │
└──────────────┴───────────────────────────────────┴───────────────────┘
```

**Left pane — live node timeline.** Server pushes `node_event` messages over WS as the graph progresses. The frontend lights up nodes in real time. Iteration scores tracked per loop so the user can watch their ATS climb (or regress).

**Center pane — current proposal.** Real word-level diff via [jsdiff](https://www.npmjs.com/package/diff)'s `diffWordsWithSpace` — red strikethrough for removed text, green highlight for added. Inline (not split-pane) so the polished sentence reads naturally with its edits in place. Keyboard: `Enter` accept, `x` reject, `f` fix, `q` quit. Fix opens an inline textarea modal; the server re-runs `revise_proposal` and the new proposal streams back into the same center pane without navigation.

**Right pane — ATS breakdown.** The multi-dim `ATSReport` from #042 rendered as a compact two-column table with status glyphs, plus a chip cloud of keyword gaps below.

### Inputs step

A pre-flight inputs form mirrors the CLI `run` flags. Required: master-or-resume + job. Advanced collapsed: facts bank YAML, style YAML, output dir, max-iter, no-enrich, no-approve. Submit opens the WebSocket session and transitions into the workspace.

### State machine

The Run session is a finite state machine driven by the WebSocket protocol from Phase 1's `WebSocketPrompter`. A zustand store (`state/run-session.ts`) buffers what the panes display:

- `phase` — what the user is currently looking at (idle / starting / running / iteration_confirm / approval / enrich_question / enrich_polished / fixing / done / error).
- `pendingPrompt` — the open server question the user must answer.
- Append-only logs — `nodeEvents`, `iterationHistory`, `statusStack`, `approvedProposals`, `rejectedProposals`.

### Discriminating prompts

The two `confirm` prompts that gate iterations ("Accept this tailored version?" and "Continue anyway?") plus the `choose` prompt that gates enrichment ("Start an enrichment session?") look the same on the wire. The controller discriminates them by message-text substring against the unchanged Phase-1 wording. The alternative — server emitting a `role` field on every prompter call — is a deliberate defer.

### Keyboard model

Global `keydown` handler scoped to the approval phase, disabled when an `INPUT`/`TEXTAREA`/modal has focus:

| Key | Action |
|---|---|
| `Enter` | Accept |
| `x` | Reject (opens reason modal — empty reason fine) |
| `f` | Fix (opens textarea — Ctrl+Enter submits) |
| `q` | Quit approval (server returns best-scoring iteration) |

## Success Metrics

- A full approval run against `data/master_resume.yaml` + a realistic JD behaves identically to the CLI — same proposals, same rejected-suggestions memory, same `facts_bank.yaml` writes.
- Every CLI keypress (`y` / `n` / `f` / `q`) has a keyboard equivalent in the GUI.
- The Fix modal round-trips in the same pane — no navigation, no lost place.
- Closing the window mid-approval cleanly tears down the WebSocket session server-side.

## Key Files

- `desktop/src/lib/events.ts` (NEW) — TS types mirroring `server/ws_prompter.py`'s message protocol.
- `desktop/src/lib/ws.ts` (NEW) — `useFlowSocket` hook.
- `desktop/src/state/run-session.ts` (NEW) — zustand store.
- `desktop/src/components/diff-view.tsx` (NEW) — word-level inline diff via jsdiff.
- `desktop/src/screens/run/index.tsx` (NEW) — orchestrator.
- `desktop/src/screens/run/{inputs,workspace,node-timeline,proposal-pane,iteration-confirm,fix-modal,rejection-modal,status-pane,ats-side-pane,use-run-controller}.tsx` (NEW).
- `desktop/src/App.tsx` — register `/run` route.
- `desktop/src/components/nav-rail.tsx` — promote Run to first item.
- `desktop/package.json` — `diff` + `@types/diff`.

## Dependencies

- **#043** (Phase 1 server) — provides the `/api/ws/run` endpoint.
- **#044** (Phase 2 shell) — provides the chrome.

## Out of Scope

- Enrichment center-pane components (Phase 4) — the placeholder is wired today.
- Bootstrap interview UI (Phase 5).

## Labels

`enhancement`, `priority:high`
