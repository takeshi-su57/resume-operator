# How to Develop

Guide for setting up, running, and contributing to resume-operator.

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

### StateGraph

The agent is a LangGraph `StateGraph` — a directed graph where:
- **State** (`ResumeOptimizerState`) flows through the graph
- **Nodes** are Python functions that read state and return updates
- **Edges** define the execution order

```python
# How the graph is built (see graph.py)
graph = StateGraph(ResumeOptimizerState)
graph.add_node("parse_resume", parse_resume)  # Register a node
graph.add_edge(START, "parse_resume")          # Define flow
compiled = graph.compile()                      # Make it runnable
result = compiled.invoke(initial_state)         # Execute
```

### Node Pattern

Every node follows the same pattern:

```python
def my_node(state: ResumeOptimizerState) -> dict:
    # 1. Read what you need from state
    data = state.some_field

    # 2. Do work (call tools, LLM, etc.)
    result = some_tool(data)

    # 3. Return ONLY the fields you're updating
    return {"output_field": result}
```

Key rules:
- Return a **dict**, not the full state — LangGraph merges it automatically
- Call **tools** for I/O, don't import external libraries directly
- Use **prompt templates** from `prompts/`, not inline strings
- **Catch exceptions** and append to `state.errors` instead of crashing

### Pipeline Flow

```
parse_resume → ats_score → analyze_gaps → optimize_content → generate_pdf → report_results
```

Each node adds data to the state. Later nodes read earlier nodes' output.

## Adding a New Node

1. Create `src/resume_operator/nodes/my_node.py` with one public function
2. Add it to `src/resume_operator/nodes/__init__.py`
3. Wire it into `src/resume_operator/graph.py`:
   ```python
   graph.add_node("my_node", my_node)
   graph.add_edge("previous_node", "my_node")
   ```
4. Update `.claude/CLAUDE.md` — Repository Layout + Agent Flow
5. Update `docs/architecture.md` — system diagram

## Adding a New Tool

1. Create `src/resume_operator/tools/my_tool.py`
2. Update `.claude/rules/architecture.md` — Tools Layer table
3. Update `.claude/CLAUDE.md` — Repository Layout

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

All external I/O must be mocked in tests:

```python
from unittest.mock import patch, MagicMock

@patch("resume_operator.tools.llm_provider.get_llm")
def test_my_node(mock_get_llm):
    # Set up mock LLM response
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = '{"key": "value"}'
    mock_get_llm.return_value = mock_llm

    # Call the node with test state
    state = ResumeOptimizerState(resume_path="test.pdf")
    result = my_node(state)

    # Verify the result
    assert "output_field" in result
```

### Fixtures

Shared fixtures in `tests/conftest.py`:
- `sample_resume` — Pre-built `ResumeData`
- `sample_job` — Pre-built `JobDescription`
- `sample_state` — Full `ResumeOptimizerState` with all fields populated

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
- **Config**: env vars via `config.py`, never hardcode
