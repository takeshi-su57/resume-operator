# [Docs]: Write "How to Develop" guide

## Description

Create a developer guide explaining how to set up the project, run it, and understand the LangGraph architecture. Target audience is a developer new to LangGraph who wants to contribute.

## Motivation

The project uses LangGraph patterns that may be unfamiliar to contributors. A clear development guide reduces onboarding friction and ensures consistent code patterns across contributors.

## Tasks

- [x] Enhance `docs/guides/development.md` with comprehensive developer onboarding content
- [x] Section: Prerequisites (Python 3.12+, uv, API key, Git)
- [x] Section: Setup (clone, install, .env configuration) with environment variables table
- [x] Section: Running the agent (CLI commands with examples for run, parse-resume, score)
- [x] Section: LangGraph concepts (StateGraph, State Model, Node Pattern, Pipeline Flow) with references to actual project files
- [x] Section: Adding a new node (6-step guide with file locations and code examples)
- [x] Section: Adding a new tool (3-step guide)
- [x] Section: Testing (commands, mocking pattern with call-site patching, fixture usage examples)
- [x] Section: Code quality (ruff check, ruff format, mypy, combined command)
- [x] Reference `docs/architectures/architecture.md` for system diagram and data flow
- [x] Section: Key Files Reference table mapping important files to their purpose
- [x] Section: Project Conventions (commits, files, types, config, logging, security)

## Acceptance Criteria

- A new developer can go from clone to running `parse-resume` by following the guide
- LangGraph concepts explained with references to actual project files
- Guide follows documentation rules from `.claude/rules/documentation.md`

## Key Files

- `docs/guides/development.md` (enhanced)
- `docs/issues/009-development-guide.md` (updated)

## Dependencies

- #006

## Labels

`documentation`, `priority:medium`
