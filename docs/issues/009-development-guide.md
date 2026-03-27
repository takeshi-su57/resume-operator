# [Docs]: Write "How to Develop" guide

## Description

Create a developer guide explaining how to set up the project, run it, and understand the LangGraph architecture. Target audience is a developer new to LangGraph who wants to contribute.

## Motivation

The project uses LangGraph patterns that may be unfamiliar to contributors. A clear development guide reduces onboarding friction and ensures consistent code patterns across contributors.

## Tasks

- [ ] Create `docs/development.md`
- [ ] Section: Prerequisites (Python 3.12+, API key)
- [ ] Section: Setup (clone, install, .env configuration)
- [ ] Section: Running the agent (CLI commands with examples)
- [ ] Section: LangGraph concepts for this project (StateGraph, nodes, edges, state, compile, invoke)
- [ ] Section: Adding a new node (step-by-step with file locations)
- [ ] Section: Adding a new tool (step-by-step)
- [ ] Section: Testing (how to run, how to mock, fixture patterns)
- [ ] Section: Code quality (ruff, mypy, pytest commands)
- [ ] Reference `docs/architecture.md` for system diagram

## Acceptance Criteria

- A new developer can go from clone to running `parse-resume` by following the guide
- LangGraph concepts explained with references to actual project files
- Guide follows documentation rules from `.claude/rules/documentation.md`

## Key Files

- `docs/development.md` (new)

## Dependencies

- #006

## Labels

`documentation`, `priority:medium`
