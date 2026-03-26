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
| [008](008-verify-langgraph-assembly.md) | Feature | Verify LangGraph graph assembly | High | 006 |
| [009](009-wire-parse-resume-cli.md) | Feature | Wire parse-resume CLI command | Medium | 006 |
| [010](010-development-guide.md) | Docs | Write "How to Develop" guide | Medium | 006 |

## Phase 3: LLM Nodes

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [011](011-implement-ats-score-node.md) | Feature | Implement and test ats_score node | High | 006 |
| [013](013-implement-analyze-gaps-node.md) | Feature | Implement and test analyze_gaps node | High | 011 |
| [014](014-implement-optimize-content-node.md) | Feature | Implement and test optimize_content node | High | 013 |
| [016](016-implement-pdf-generator.md) | Feature | Implement and test PDF generation tool | High | 001 |

## Phase 4: Pipeline Completion

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [018](018-implement-generate-pdf-node.md) | Feature | Implement and test generate_pdf node | High | 016 |
| [019](019-implement-report-results-node.md) | Feature | Implement and test report_results node | High | 014 |
| [021](021-full-pipeline-integration-test.md) | Feature | Full pipeline integration test | High | 018, 019 |
| [022](022-wire-run-score-cli.md) | Feature | Wire run + score CLI commands | High | 021 |

## Phase 5: Robustness and Quality

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [023](023-add-structured-logging.md) | Feature | Add structured logging | Medium | 022 |
| [024](024-input-validation-error-messages.md) | Feature | Input validation + error messages | Medium | 022 |
| [025](025-llm-json-extraction-utility.md) | Chore | LLM JSON extraction utility | Medium | 014 |
| [026](026-setup-ci-quality-gates.md) | Chore | Set up CI quality gates | Medium | 021 |

## Phase 6: Polish and Deployment

| # | Type | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| [027](027-deployment-guide.md) | Docs | Write "How to Deploy" guide | Medium | 022 |
| [028](028-conditional-routing-skip-optimization.md) | Feature | Conditional routing (skip optimization) | Low | 021 |

## Dependency Graph

```
001 ──┬── 002 ── 003
      ├── 004 ── 005
      └── 016 ── 018
                  │
002 + 004 ── 006 ──┬── 008
                    ├── 009
                    ├── 010
                    └── 011 ── 013 ── 014
                                       │
                              019 ─────┘
                               │
                    018 + 019 ── 021 ──┬── 022 ──┬── 023
                                       │         ├── 024
                                       │         └── 027
                                       ├── 026
                                       └── 028
                    014 ── 025
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
