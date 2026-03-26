# Documentation Rules

How to structure, maintain, and keep documentation in sync with the evolving system.

## Docs Location

Documentation lives in `docs/` at the repo root as simple Markdown files.

```
docs/
├── architecture.md          ← System architecture overview (living doc)
└── adr/                     ← Architecture Decision Records (append-only)
    └── yyyy-mm-dd-<name>.md
```

## Architecture Overview (`docs/architecture.md`)

The living document describing the current system state. Must contain:
- System diagram (ASCII)
- Agent flow description
- Component descriptions
- Data flow
- Current limitations

Update in the same PR that changes the architecture.

## Architecture Decision Records (ADRs)

ADRs capture **why** decisions were made. Append-only — never deleted, only superseded.

### File naming
```
docs/adr/yyyy-mm-dd-<name>.md
```

### Template
```markdown
# <Title>

**Date:** yyyy-mm-dd
**Status:** accepted | superseded by [link] | deprecated

## Context
What problem or situation requires a decision?

## Decision
What did we decide and why?

## Consequences
What are the trade-offs?
```

### When to write an ADR
- Choosing a framework or major dependency
- Changing the agent flow or graph structure
- Adding a new tool or integration
- Any decision someone might question later

### When NOT to write an ADR
- Bug fixes, adding test cases, minor refactors

## Sync Protocol

### When architecture changes
1. Update `docs/architecture.md`
2. Write an ADR if significant
3. Update `.claude/CLAUDE.md` Architecture Patterns section
4. Update `README.md` if it affects project structure or commands

### When environment variables change
1. Update `.env.example`
2. Update `config.py`
3. Update `README.md` env vars table

### When commands change
1. Update `README.md` commands section
2. Update `.claude/CLAUDE.md` Key Commands section

## Anti-Patterns

- Aspirational docs — describe what IS, not what's planned
- Duplicating content — link instead of copy
- Stale docs — update in the same PR as the code change
