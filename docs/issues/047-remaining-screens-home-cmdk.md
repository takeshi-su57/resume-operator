# [Feature]: Bootstrap, parse-resume, extract-style screens + home dashboard + cmdk — Phase 5 of desktop GUI

GitHub issue: [#88](https://github.com/takeshi-su57/resume-operator/issues/88) · PR [#94](https://github.com/takeshi-su57/resume-operator/pull/94)

## Description

Phases 1-4 (#043-#046) deliver the high-value path: Settings, Score, Run with approval loop, Enrichment interview. This phase fills in the remaining three CLI commands as GUI screens and adds a home dashboard + command palette so the app feels cohesive instead of four disconnected screens.

## Motivation

Coverage. Every CLI command should have a GUI counterpart so the app is the user's daily driver, not a partial port. The home dashboard + cmd-K palette glue everything together — they're the navigation surfaces a Linear-style app expects.

## Target State

### Home (`/`)

Landing screen. Engine-status banner (online with provider/model, or offline with the sidecar-start hint) and a 3×2 grid of quick-action tiles, one per screen. "Tailor a resume" is the primary tile (accent-tinted); everything else is a secondary tile. Recent applications feed is intentionally deferred — would need either a server-side `/api/applications` listing route or `@tauri-apps/plugin-fs`, neither of which unblocks anything in the roadmap.

### Bootstrap (`/bootstrap`)

Wraps the CLI `bootstrap` command (#019, #036) over `/api/ws/bootstrap`. Two-pane layout: left rail collects PDF + output path + skip-interview flag; right pane shows the activity log and the open prompt panel.

Reuses the same `useFlowSocket` hook as the Run screen, with a simplified linear protocol — no node timeline, no approval loop, no enrichment. Confirm / choose / text prompts each get their own minimal control; panels and notices accumulate into the activity feed above. On `done`, a green output-path footer; on `error`, a red message footer.

### Parse Resume (`/parse`)

Wraps `parse-resume`. Single PDF picker → `POST /api/parse-resume` → fields panel showing name / email / phone / summary / skills + counts (experience / education / certifications). Read-only inspection.

### Extract Style (`/style`)

Wraps `extract-style` (#037). .docx picker + optional output YAML path → `POST /api/extract-style` → preview panel showing font family, margins, and the three font sizes. When output path is set, a green "wrote …" banner confirms the YAML was persisted.

### Cmd-K palette

Global keyboard hook on `cmd/ctrl+K` toggles a Linear/Raycast-style palette. Phase 5 ships navigation only (one entry per screen); recent runs + arbitrary actions stay on the roadmap. Mounted at the App shell so any screen can fire it. Keyboard footer shows arrows / Enter / Esc / cmd-K hints.

### API client extension

`lib/api.ts` gains `useParseResume` and `useExtractStyle` mutations + their matching response types. The Bootstrap screen uses the existing `useFlowSocket` hook directly — its protocol is specific enough that the `useRunController` pattern from the Run screen would over-engineer it.

### Nav rail cleanup

Every item is now enabled; the Phase-3-5 disabled stubs are gone. Cmd-K hint sits at the bottom. Default route `/` is Home.

## Success Metrics

- Every CLI command (`run`, `score`, `parse-resume`, `bootstrap`, `extract-style`) has a GUI counterpart with equivalent behavior.
- Running the Bootstrap flow against a sample PDF produces the same `master_resume.yaml` as the CLI.
- `cmd+K` opens reliably from any screen and Enter navigates.
- App feels cohesive — shared chrome, same keyboard conventions, same aesthetic.

## Key Files

- `desktop/src/screens/{home,bootstrap,parse-resume,extract-style}.tsx` (NEW).
- `desktop/src/components/command-palette.tsx` (NEW).
- `desktop/src/lib/api.ts` — `useParseResume`, `useExtractStyle` mutations + types.
- `desktop/src/App.tsx` — register routes, mount palette.
- `desktop/src/components/nav-rail.tsx` — clean up disabled stubs, add cmd-K hint.
- `desktop/package.json` — `cmdk`.

## Dependencies

- **#043** (Phase 1 server) — provides `/api/parse-resume`, `/api/extract-style`, `/api/ws/bootstrap`.
- **#044** (Phase 2 shell) — provides the chrome.

## Out of Scope

- Recent applications feed on the home screen — deferred (needs server-side listing or `@tauri-apps/plugin-fs`).
- Cmd-K actions beyond navigation — recent-run jumps, arbitrary shortcuts. Add when the home feed lands.

## Labels

`enhancement`, `priority:high`
