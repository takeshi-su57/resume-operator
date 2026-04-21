# resume-operator — Project Context

**Project name:** resume-operator

Resume Optimizer AI Agent. User provides a hand-maintained `master_resume.yaml` (bootstrapped once from a PDF) and a job description (text) — the agent scores ATS compatibility, analyzes gaps, optimizes content, and generates a tailored PDF. The legacy PDF-input path (`--resume`) is kept for back-compat.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| Agent Framework | LangGraph (StateGraph) |
| LLM | LangChain (OpenAI / Anthropic / Google / OpenRouter — configurable) |
| PDF Parsing (input) | PyMuPDF (fitz) |
| PDF Generation (output) | ReportLab |
| CLI | Typer + Rich |
| Package Manager | uv |
| Config | Pydantic Settings + python-dotenv |
| Linting | Ruff |
| Type Checking | mypy (strict) |
| Testing | pytest + pytest-asyncio |
| Storage | Local JSON files |

## Repository Layout

```
src/resume_operator/         → Main Python package
  main.py                    → CLI entry point (Typer app)
  config.py                  → Pydantic Settings (env var bindings)
  state.py                   → ResumeOptimizerState model (central data contract)
  graph.py                   → LangGraph StateGraph assembly
  nodes/                     → Graph node functions (one per file)
    load_master.py           → Read master_resume.yaml into state (no LLM)
    parse_resume.py          → Legacy: PDF → ResumeData via LLM
    ats_score.py             → Score resume ATS compatibility vs job description
    analyze_gaps.py          → Identify gaps, strengths, improvement suggestions
    optimize_content.py      → LLM-based resume content optimization
    generate_pdf.py          → Render optimized resume to PDF via ReportLab
    report_results.py        → Save results to JSON
  tools/                     → Utility modules (I/O, external services)
    master_resume.py         → YAML load/save + ResumeData→ResumeMaster conversion
    pdf_parser.py            → PyMuPDF text extraction
    pdf_generator.py         → ReportLab PDF creation
    llm_provider.py          → LangChain model factory
  prompts/                   → LLM prompt templates as Python constants
tests/                       → pytest test suite
data/                        → Runtime data: results, generated PDFs (git-ignored)
docs/                        → Architecture docs + ADRs
```

## Architecture Patterns

**LangGraph StateGraph** — The agent is a compiled StateGraph. `ResumeOptimizerState` (Pydantic model in `state.py`) flows through nodes. Each node is a function: `(state) -> dict` returning only the fields to update. LangGraph merges updates. See `.claude/rules/architecture.md`.

**Agent flow** — `(load_master | parse_resume) → ats_score → [conditional: skip if score ≥ threshold] → analyze_gaps → optimize_content → generate_pdf → report_results`. Entry node is chosen by a conditional edge on `state.master_path`.

**Node design** — One public function per file in `nodes/`. Pure logic: receive state, call tools, return state delta. No global mutable state. Errors recorded in `state.errors`, pipeline continues.

**Tools layer** — Nodes call tools for I/O. `tools/llm_provider.py` returns a LangChain `BaseChatModel` based on `LLM_PROVIDER` env var. `tools/pdf_parser.py` wraps PyMuPDF for input. `tools/pdf_generator.py` wraps ReportLab for output.

**Prompts** — String templates in `prompts/` as Python constants with `{placeholder}` fields. One file per concern (resume parsing, ATS scoring, gap analysis, content optimization).

**Config** — All config via env vars loaded by Pydantic Settings (`config.py`). `.env` file supported via python-dotenv. See `.env.example` for all variables.

**Storage** — Local JSON files in `data/`. Results written after each run. No database.

**CLI** — Typer app in `main.py` with Rich for progress display. Commands: `run`, `bootstrap`, `parse-resume`, `score`. `run` and `score` accept `--master` (preferred) or `--resume` (legacy).

## Key Commands

```bash
uv sync --dev              # Install with dev dependencies
uv run python -m resume_operator bootstrap --resume old.pdf --output data/master_resume.yaml  # One-time
uv run python -m resume_operator run --master data/master_resume.yaml --job job.txt           # Full pipeline
uv run python -m resume_operator parse-resume --resume resume.pdf                              # Parse PDF (legacy)
uv run python -m resume_operator score --master data/master_resume.yaml --job job.txt          # ATS score only
uv run pytest              # Run tests
uv run ruff check src/ tests/     # Lint
uv run ruff format src/ tests/    # Format
uv run mypy src/           # Type check
```

## Conventions

- **Commits:** Conventional commits — `type(scope): description`
- **File naming:** snake_case for files, PascalCase for classes
- **Typing:** strict mypy, all functions typed
- **Linting:** Ruff (line-length 100, Python 3.12 target)
- **Config:** Never hardcode API keys — use env vars via `config.py`

## Rules (Detailed Guidance)

- `.claude/rules/architecture.md` — LangGraph patterns, node design, tools layer, state, anti-patterns
- `.claude/rules/testing.md` — pytest strategy, mocking patterns, fixtures, coverage targets
- `.claude/rules/security.md` — API key management, .env handling, personal data
- `.claude/rules/git-commit.md` — Conventional commit format, types, examples
- `.claude/rules/pull-request.md` — PR title format, description template, size guidelines
- `.claude/rules/gh-issue.md` — Issue title format, templates for bugs/features/chores
- `.claude/rules/ai-framework.md` — Sync protocol, skill/rule design, maintenance
- `.claude/rules/documentation.md` — Docs structure, ADR conventions
- `.claude/rules/logging.md` — Log levels, node logging pattern, LLM call logging, CLI verbosity

## Known Gaps

- Node implementations are stubs (TODO placeholders)
- No CI pipeline yet
- No LangGraph checkpointing configured yet (needed for resume on crash)
- PDF template customization not designed yet
- No batch mode (multiple jobs per run) — state model ready for future support
