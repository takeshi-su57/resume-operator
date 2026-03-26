# AI Engineering Framework

This repository uses AI-assisted development with structured guidelines to ensure consistent architecture, testing, and security standards.

## Philosophy

1. AI tools operate within defined architectural boundaries — they follow the patterns in `.claude/rules/`
2. AI-generated code must pass the same quality checks as human code (ruff, mypy, pytest)
3. Conventions are documented, not implied — see `.claude/CLAUDE.md` for the index
4. Human review is always the final gate

## Framework Structure

| File | Purpose |
|------|---------|
| `.claude/CLAUDE.md` | AI context — auto-loaded, concise index (< 200 lines) |
| `.claude/rules/architecture.md` | LangGraph patterns, node design, tools layer, state, anti-patterns |
| `.claude/rules/testing.md` | pytest strategy, mocking, fixtures, coverage targets |
| `.claude/rules/security.md` | API keys, env vars, personal data handling |
| `.claude/rules/documentation.md` | Docs structure, ADR conventions, sync protocol |
| `.claude/rules/ai-framework.md` | Framework maintenance, sync protocol, design principles |
| `.claude/rules/git-commit.md` | Conventional commit format |
| `.claude/rules/pull-request.md` | PR format and size guidelines |
| `.claude/rules/gh-issue.md` | Issue templates (bug, feature, chore) |
| `.claude/skills/write-adr/` | Skill: write Architecture Decision Records |

## Core Engineering Principles

1. **LangGraph StateGraph** — Agent is a compiled graph with typed Pydantic state
2. **Nodes as pure functions** — `(state) -> dict` returning only changed fields
3. **Tools layer for I/O** — Nodes delegate external calls to `tools/` modules
4. **Prompts as templates** — LLM prompts are string constants in `prompts/`, not inline
5. **Config via env vars** — Pydantic Settings with `.env` support, never hardcode
6. **No global mutable state** — All data flows through `ResumeOptimizerState`
7. **Strict typing** — mypy strict mode, all functions typed
8. **Ruff for quality** — Lint + format in one tool (line-length 100, Python 3.12)

## AI Coding Expectations

When generating code for this project:
- Follow the node pattern in `.claude/rules/architecture.md`
- Use `tools/llm_provider.py` for LLM calls, not direct imports
- Use `tools/pdf_parser.py` for PDF input, `tools/pdf_generator.py` for PDF output
- Use `config.py` for all configuration, not `os.environ`
- Use prompt templates from `prompts/`, not inline strings
- Include type hints on all functions
- Never hardcode API keys or personal data

## Maintaining This Framework

See `.claude/rules/ai-framework.md` for the full sync protocol. Key points:
- Keep `CLAUDE.md` under 200 lines
- Update rules when code patterns change
- Rules reference real code, not generic advice
- Remove stale rules — wrong guidance is worse than none
