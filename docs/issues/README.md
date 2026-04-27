# Implementation Roadmap

23 issues organized into 6 phases. Each phase builds on the previous, designed so a LangGraph beginner can follow from zero to deployment.

## Phase 1: Foundation (No LangGraph knowledge needed)

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [001](001-setup-dev-environment.md) | Chore | Set up dev environment | High | — |
| [002](002-implement-pdf-parser.md) | Feature | Implement PDF text extraction | High | 001 |
| [003](003-test-pdf-parser.md) | Feature | Test pdf_parser tool | High | 002 |
| [004](004-implement-llm-provider.md) | Feature | Implement LLM provider factory | High | 001 |
| [005](005-test-llm-provider-config.md) | Feature | Test llm_provider and config | High | 004 |

## Phase 2: First Node + LangGraph Basics

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [006](006-implement-parse-resume-node.md) | Feature | Implement and test parse_resume node | High | 002, 004 |
| [007](007-verify-langgraph-assembly.md) | Feature | Verify LangGraph graph assembly | High | 006 |
| [008](008-wire-parse-resume-cli.md) | Feature | Wire parse-resume CLI command | Medium | 006 |
| [009](009-development-guide.md) | Docs | Write "How to Develop" guide | Medium | 006 |

## Phase 3: LLM Nodes

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [010](010-implement-ats-score-node.md) | Feature | Implement and test ats_score node | High | 006 |
| [011](011-implement-analyze-gaps-node.md) | Feature | Implement and test analyze_gaps node | High | 010 |
| [012](012-implement-optimize-content-node.md) | Feature | Implement and test optimize_content node | High | 011 |
| [013](013-implement-pdf-generator.md) | Feature | Implement and test PDF generation tool | High | 001 |

## Phase 4: Pipeline Completion

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [014](014-implement-generate-pdf-node.md) | Feature | Implement and test generate_pdf node | High | 013 |
| [015](015-implement-report-results-node.md) | Feature | Implement and test report_results node | High | 012 |
| [016](016-full-pipeline-integration-test.md) | Feature | Full pipeline integration test | High | 014, 015 |
| [017](017-wire-run-score-cli.md) | Feature | Wire run + score CLI commands | High | 016 |

## Phase 5: Robustness and Quality

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [018](018-add-structured-logging.md) | Feature | Add structured logging | Medium | 017 |
| [019](019-input-validation-error-messages.md) | Feature | Input validation + error messages | Medium | 017 |
| [020](020-llm-json-extraction-utility.md) | Chore | LLM JSON extraction utility | Medium | 012 |
| [021](021-setup-ci-quality-gates.md) | Chore | Set up CI quality gates | Medium | 016 |

## Phase 6: Polish and Deployment

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [022](022-deployment-guide.md) | Docs | Write "How to Deploy" guide | Medium | 017 |
| [023](023-conditional-routing-skip-optimization.md) | Feature | Conditional routing (skip optimization) | Low | 016 |

## Phase 7: v2 — Structured source of truth (rework)

Driven by a post-v1 review that surfaced the architectural gap: the system re-parses a PDF every run instead of maintaining a structured master. See [luckyplans plan 002](../../../../luckyplans/plans/002-resume-ats-tailor/plan.md) for context.

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [024](024-master-resume-yaml-source-of-truth.md) | Feature | `master_resume.yaml` as source of truth | High | — |
| [025](025-facts-bank-yaml.md) | Feature | `facts_bank.yaml` for items beyond master | High | 024 |
| [026](026-tailored-resume-item-level-references.md) | Refactor | `TailoredResume` with item-level references | High | 024, 028 |
| [027](027-deterministic-pdf-render.md) | Refactor | Deterministic PDF render from structured data | Medium | 026 |
| [028](028-langchain-structured-output.md) | Refactor | `with_structured_output` (drop manual JSON parsing) | Medium | — |
| [029](029-per-application-output-folder.md) | Feature | Per-application versioned output folder | Medium | 026 |

## Phase 8: Desktop GUI

Driven by the observation that the iterative approval loop (#040) and enrichment interview (#033) — the highest-value moments in the tool — are flattened by the terminal. A six-PR effort to ship a Tauri 2 + React desktop app that exposes every CLI command as a screen, with a pro/dense Linear-style UI. The CLI stays as a peer surface; both invoke the same compiled LangGraph and the same flows behind a `Prompter` seam.

| # | Type | Title | Priority | Depends On | GitHub |
|---|------|-------|----------|------------|--------|
| [043](043-fastapi-server-for-desktop-gui.md) | Feature | FastAPI + WebSocket server wrapping the tailor graph | High | 040, 042 | [#84](https://github.com/takeshi-su57/resume-operator/issues/84) / [PR #90](https://github.com/takeshi-su57/resume-operator/pull/90) |
| [044](044-tauri-shell-settings-score.md) | Feature | Tauri 2 shell + Settings + Score screens | High | 043 | [#85](https://github.com/takeshi-su57/resume-operator/issues/85) / [PR #91](https://github.com/takeshi-su57/resume-operator/pull/91) |
| [045](045-run-screen-approval-workspace.md) | Feature | Three-pane Run workspace + approval loop | High | 044 | [#86](https://github.com/takeshi-su57/resume-operator/issues/86) / [PR #92](https://github.com/takeshi-su57/resume-operator/pull/92) |
| [046](046-enrichment-interview-cards.md) | Feature | Enrichment interview card stack | High | 045 | [#87](https://github.com/takeshi-su57/resume-operator/issues/87) / [PR #93](https://github.com/takeshi-su57/resume-operator/pull/93) |
| [047](047-remaining-screens-home-cmdk.md) | Feature | Bootstrap / Parse / Style / Home / cmd-K | High | 046 | [#88](https://github.com/takeshi-su57/resume-operator/issues/88) / [PR #94](https://github.com/takeshi-su57/resume-operator/pull/94) |
| [048](048-pyinstaller-tauri-msi.md) | Feature | PyInstaller sidecar + Tauri MSI installer | High | 047 | [#89](https://github.com/takeshi-su57/resume-operator/issues/89) / [PR #95](https://github.com/takeshi-su57/resume-operator/pull/95) |

## Dependency Graph

```
001 ──┬── 002 ── 003
      ├── 004 ── 005
      └── 013 ── 014
                  │
002 + 004 ── 006 ──┬── 007
                    ├── 008
                    ├── 009
                    └── 010 ── 011 ── 012
                                       │
                              015 ─────┘
                               │
                    014 + 015 ── 016 ──┬── 017 ──┬── 018
                                       │         ├── 019
                                       │         └── 022
                                       ├── 021
                                       └── 023
                    012 ── 020
```

## LangGraph Learning Path

| Phase | What You Learn |
|-------|---------------|
| 1 | Python project setup, tools layer, testing — no LangGraph yet |
| 2 | State, nodes, edges, compile, invoke — LangGraph fundamentals |
| 3 | Multi-node state flow, LLM integration patterns |
| 4 | Full graph execution, integration testing, CLI wiring |
| 5 | Production quality: logging, validation, robustness |
| 6 | Conditional edges (advanced), deployment |
