# How to Develop

Guide for setting up, running, and contributing to resume-operator.

For the system architecture diagram and data flow, see [docs/architectures/architecture.md](../architectures/architecture.md).

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- An LLM API key (OpenAI, Anthropic, Google, or OpenRouter)
- Git

## Setup

```bash
# Clone the repo
git clone <repo-url>
cd resume-operator

# Install with dev dependencies (creates .venv automatically)
uv sync --dev

# Configure environment
cp .env.example .env
# Edit .env — add your LLM API key
```

### Environment Variables

All configuration is managed through environment variables loaded by Pydantic Settings
in `src/resume_operator/config.py`. See `.env.example` for the full list:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM backend: `openai`, `anthropic`, `google`, or `openrouter` |
| `LLM_MODEL` | `gpt-4o` | Model name passed to the provider |
| `OPENAI_API_KEY` | — | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |
| `GOOGLE_API_KEY` | — | Required if `LLM_PROVIDER=google` |
| `OPENROUTER_API_KEY` | — | Required if `LLM_PROVIDER=openrouter` |
| `LOG_LEVEL` | `INFO` | Python logging level |

You only need **one** API key — the one matching your chosen `LLM_PROVIDER`.

## Running the Agent

```bash
# Full optimization pipeline
uv run python -m resume_operator run --resume resume.pdf --job job_description.txt

# Parse resume only (no job description needed)
uv run python -m resume_operator parse-resume --resume resume.pdf

# ATS score only (quick check)
uv run python -m resume_operator score --resume resume.pdf --job job_description.txt

# Show all commands
uv run python -m resume_operator --help
```

## LangGraph Concepts for This Project

If you're new to LangGraph, here's how the key concepts map to this project.

### StateGraph

The agent is a LangGraph `StateGraph` — a directed graph where:
- **State** (`ResumeOptimizerState` in `src/resume_operator/state.py`) flows through the graph
- **Nodes** are Python functions that read state and return updates (in `src/resume_operator/nodes/`)
- **Edges** define the execution order

The graph is assembled in `src/resume_operator/graph.py`:

```python
# How the graph is built (see src/resume_operator/graph.py)
graph = StateGraph(ResumeOptimizerState)
graph.add_node("parse_resume", parse_resume)  # Register a node
graph.add_edge(START, "parse_resume")          # Define flow
compiled = graph.compile()                      # Make it runnable
result = compiled.invoke(initial_state)         # Execute
```

**`compile()`** validates the graph and returns a runnable object. **`invoke()`** runs the
full pipeline, passing the state through each node in edge order. Each node receives the
full state and returns a dict of fields to update — LangGraph merges the update into the
state automatically.

### State Model

`ResumeOptimizerState` in `src/resume_operator/state.py` is the single data contract.
All sub-models (`ResumeData`, `JobDescription`, `ATSScore`, `GapAnalysis`, `OptimizedResume`)
are Pydantic `BaseModel` classes with typed fields and defaults. Nodes read from state and
return only the fields they update.

### Node Pattern

Every node follows the same pattern (one function per file in `src/resume_operator/nodes/`):

```python
# src/resume_operator/nodes/my_node.py
import logging
from typing import Any
from resume_operator.state import ResumeOptimizerState

logger = logging.getLogger(__name__)

def my_node(state: ResumeOptimizerState) -> dict[str, Any]:
    logger.info("my_node: starting")

    # 1. Read what you need from state
    data = state.some_field

    # 2. Do work (call tools, LLM, etc.)
    result = some_tool(data)

    # 3. Return ONLY the fields you're updating
    logger.info("my_node: completed — key_metric=%s", metric)
    return {"output_field": result}
```

Key rules:
- Return a **dict**, not the full state — LangGraph merges it automatically
- Call **tools** (`src/resume_operator/tools/`) for I/O, don't import external libraries directly
- Use **prompt templates** from `src/resume_operator/prompts/`, not inline strings
- **Catch exceptions** and append to `state.errors` instead of crashing
- **Log** entry/exit at INFO level (see `.claude/rules/logging.md`)

For a complete working example, see `src/resume_operator/nodes/parse_resume.py`.

### Pipeline Flow

```
START → parse_resume → ats_score → analyze_gaps → optimize_content → generate_pdf → report_results → END
```

Each node adds data to the state. Later nodes read earlier nodes' output. For the full
data flow diagram, see [docs/architectures/architecture.md](../architectures/architecture.md).

## Adding a New Node

1. **Create the node file** — `src/resume_operator/nodes/my_node.py` with one public function
   following the node pattern above. Use tools from `src/resume_operator/tools/` for I/O
   and prompts from `src/resume_operator/prompts/` for LLM calls.

2. **Export it** — Add the import to `src/resume_operator/nodes/__init__.py`:
   ```python
   from resume_operator.nodes.my_node import my_node
   ```

3. **Wire it into the graph** — Edit `src/resume_operator/graph.py`:
   ```python
   graph.add_node("my_node", my_node)
   graph.add_edge("previous_node", "my_node")
   graph.add_edge("my_node", "next_node")
   ```

4. **Add state fields** — If the node produces new data, add the corresponding Pydantic
   model and field to `src/resume_operator/state.py`.

5. **Write tests** — Create `tests/test_my_node.py`. Mock all tools (`get_llm`,
   `extract_text`, etc.) and use fixtures from `tests/conftest.py`.

6. **Update docs** — Update `.claude/CLAUDE.md` (Repository Layout + Agent Flow) and
   `docs/architectures/architecture.md` (system diagram).

## Adding a New Tool

1. **Create the tool file** — `src/resume_operator/tools/my_tool.py`. Tools handle external
   I/O (files, APIs, LLMs). Keep them focused — one concern per file.

2. **Use it from nodes** — Import the tool in your node and call it. Nodes call tools;
   tools never call nodes.

3. **Update docs** — Update `.claude/rules/architecture.md` (Tools Layer table) and
   `.claude/CLAUDE.md` (Repository Layout).

## Testing

```bash
# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_state.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run coverage run -m pytest && uv run coverage report
```

### Mocking Pattern

All external I/O must be mocked in tests. Patch at the **call site**, not the definition:

```python
from unittest.mock import patch, MagicMock

# Patch where the function is used (in the node), not where it's defined (in tools/)
@patch("resume_operator.nodes.my_node.get_llm")
@patch("resume_operator.nodes.my_node.extract_text")
def test_my_node(mock_extract, mock_get_llm):
    # Mock PDF extraction
    mock_extract.return_value = "Jane Smith\njane@example.com\n..."

    # Mock LLM response
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = '{"key": "value"}'
    mock_get_llm.return_value = mock_llm

    # Call the node with test state
    state = ResumeOptimizerState(resume_path="test.pdf")
    result = my_node(state)

    # Verify the result
    assert "output_field" in result
```

For a full working test example, see `tests/test_parse_resume.py`.

### Fixtures

Shared fixtures in `tests/conftest.py`:
- `sample_resume` — Pre-built `ResumeData` with realistic fields
- `sample_job` — Pre-built `JobDescription` with requirements and keywords
- `sample_state` — Full `ResumeOptimizerState` with resume + job + analysis populated

Use these to avoid boilerplate in node tests:

```python
def test_uses_resume_from_state(self, sample_state):
    result = my_node(sample_state)
    assert result["some_field"] is not None
```

## Code Quality

```bash
# Lint (check for issues)
uv run ruff check src/ tests/

# Format (auto-fix formatting)
uv run ruff format src/ tests/

# Type check (strict mode)
uv run mypy src/

# Run everything
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/ && uv run pytest
```

## Project Conventions

- **Commits**: `type(scope): description` — see `.claude/rules/git-commit.md`
- **Files**: snake_case for files, PascalCase for classes
- **Types**: strict mypy, all functions typed
- **Config**: env vars via `src/resume_operator/config.py`, never hardcode
- **Logging**: use `logging.getLogger(__name__)`, never `print()` — see `.claude/rules/logging.md`
- **Security**: never commit API keys or personal data — see `.claude/rules/security.md`

## Key Files Reference

| File | Purpose |
|------|---------|
| `src/resume_operator/main.py` | CLI entry point (Typer app) |
| `src/resume_operator/config.py` | Pydantic Settings — env var bindings |
| `src/resume_operator/state.py` | `ResumeOptimizerState` — central data contract |
| `src/resume_operator/graph.py` | LangGraph StateGraph assembly |
| `src/resume_operator/nodes/` | One node function per file |
| `src/resume_operator/tools/` | I/O utilities (PDF parsing, LLM, PDF generation) |
| `src/resume_operator/prompts/` | LLM prompt templates as string constants |
| `tests/conftest.py` | Shared pytest fixtures |
| `.env.example` | Environment variable template |
| `docs/architectures/architecture.md` | System diagram and data flow |
