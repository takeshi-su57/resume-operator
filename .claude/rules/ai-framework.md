# AI Framework Maintenance Rules

How to maintain and evolve the AI engineering framework (`.claude/`, `AI_ENGINEERING.md`).

## Framework File Hierarchy

```
AI_ENGINEERING.md              ← Human-readable overview
.claude/
├── CLAUDE.md                  ← AI context (auto-loaded, < 200 lines)
├── rules/                     ← Detailed guidance documents
│   └── <topic>.md
├── skills/                    ← Reusable task patterns
│   └── <skill-name>/
│       ├── skill.md
│       ├── templates/
│       └── examples/
└── settings.local.json        ← Claude Code permissions
```

## Sync Protocol

### When architecture changes (new node, tool, or pattern)
1. Update `.claude/rules/architecture.md`
2. Update `.claude/CLAUDE.md` — Architecture Patterns + Agent Flow
3. Update `AI_ENGINEERING.md` — Core Principles section
4. Update `README.md` — if project structure or commands change
5. Update `docs/architecture.md` — system diagram

### When adding a new node
1. Create `src/resume_operator/nodes/<name>.py`
2. Add to `nodes/__init__.py`
3. Wire into `graph.py`
4. Update `.claude/CLAUDE.md` — Repository Layout + Agent Flow
5. Update `docs/architecture.md` — agent flow diagram

### When adding a new tool
1. Create `src/resume_operator/tools/<name>.py`
2. Update `.claude/rules/architecture.md` — Tools Layer table
3. Update `.claude/CLAUDE.md` — Repository Layout

### When environment variables change
1. Update `.env.example`
2. Update `src/resume_operator/config.py` — Settings class
3. Update `README.md` — env vars table

### When adding a new rule
1. Create `.claude/rules/<topic>.md`
2. Add reference in `.claude/CLAUDE.md` under Rules section
3. Add row in `AI_ENGINEERING.md` Framework Structure table

### When adding a new skill
1. Create `.claude/skills/<skill-name>/` with `skill.md`, `templates/`, `examples/`
2. Add row in `AI_ENGINEERING.md` Framework Structure table

## Post-Implementation Checklist

After completing any implementation task, verify:

### Files to check
- [ ] `.claude/CLAUDE.md` — Tech Stack, Repository Layout, Architecture Patterns, Key Commands, Known Gaps
- [ ] `README.md` — project structure, commands, env vars
- [ ] `docs/architecture.md` — if architecture changed
- [ ] Write ADR if it's a significant decision

### Quality checks
```bash
ruff check src/ tests/     # Lint
ruff format src/ tests/    # Format
mypy src/                  # Type check
pytest                     # Tests
```

## CLAUDE.md Principles

- **Under 200 lines** — bloating degrades AI performance
- **An index, not a manual** — summarize, point to rules for details
- **Factual, not aspirational** — describe what IS, not what should be
- **No duplicated content** — if it's in a rule file, don't repeat it

## Rule Design Principles

- Reference real code in this codebase, not generic advice
- Show concrete examples from existing code
- State anti-patterns explicitly ("do NOT")
- Stay current — outdated rules are worse than no rules
- One topic per file

## Skill Design Principles

- Solve a repeatable task done more than once
- Templates use `.md` files with `{placeholder}` markers
- Examples show a complete worked scenario
- Include what to import and from where
