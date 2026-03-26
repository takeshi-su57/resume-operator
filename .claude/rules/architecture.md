# Architecture Rules

## Project Structure

resume-operator is a single Python package, not a monorepo. All source code lives in `src/resume_operator/`.

```
src/resume_operator/
├── main.py              # CLI entry point (Typer)
├── config.py            # Pydantic Settings
├── state.py             # ResumeOptimizerState — central data contract
├── graph.py             # LangGraph StateGraph assembly
├── nodes/               # Graph node functions
├── tools/               # I/O utilities (PDF, LLM)
└── prompts/             # LLM prompt templates
```

## LangGraph StateGraph

The agent is built as a LangGraph `StateGraph` compiled into a runnable graph.

- **State**: `ResumeOptimizerState` in `state.py` — a Pydantic `BaseModel` that flows through all nodes
- **Nodes**: Functions registered via `graph.add_node("name", function)`
- **Edges**: Linear (`add_edge`) for v1; conditional edges planned for future batch mode
- **Compilation**: `graph.compile()` returns a runnable that accepts initial state

### Agent Flow

```
START → parse_resume → ats_score → analyze_gaps → optimize_content → generate_pdf → report_results → END
```

Linear pipeline in v1. Future batch mode will add a loop over multiple job descriptions using conditional edges and `current_job_index`.

## Node Design Pattern

Each node is a module in `nodes/` with a single public function:

```python
# nodes/example_node.py
from resume_operator.state import ResumeOptimizerState

def example_node(state: ResumeOptimizerState) -> dict:
    """Node description."""
    # 1. Read from state
    # 2. Call tools (PDF, LLM, etc.)
    # 3. Return ONLY the fields to update
    return {"field_name": new_value}
```

Rules:
- **One function per file** — the file name matches the function name
- **Return a dict** of state fields to update, not the full state. LangGraph handles merging.
- **No global mutable state** — all data flows through `ResumeOptimizerState`
- **Errors don't crash the pipeline** — catch exceptions, append to `state.errors`, continue
- **No direct I/O in nodes** — delegate to tools layer (`tools/`)

## Tools Layer

Tools are utility modules that handle external I/O. Nodes call tools; tools don't call nodes.

| Tool | File | Purpose |
|------|------|---------|
| PDF Parser | `tools/pdf_parser.py` | Extract text from PDF via PyMuPDF |
| PDF Generator | `tools/pdf_generator.py` | Generate resume PDF via ReportLab |
| LLM Provider | `tools/llm_provider.py` | LangChain model factory (configurable provider) |

### LLM Provider

`get_llm()` returns a LangChain `BaseChatModel` based on the `LLM_PROVIDER` env var. Supports `openai`, `anthropic`, `google`. Provider-specific packages are imported lazily.

### PDF Parser

Wraps PyMuPDF (fitz) for text extraction:

```python
from resume_operator.tools.pdf_parser import extract_text

text = extract_text(Path("resume.pdf"))
```

### PDF Generator

Wraps ReportLab for PDF creation:

```python
from resume_operator.tools.pdf_generator import generate_pdf

output = generate_pdf(sections={"experience": "..."}, output_path=Path("output.pdf"))
```

## Prompts

LLM prompt templates live in `prompts/` as Python string constants with `{placeholder}` fields:

```python
# prompts/ats_scoring.py
ATS_SCORE = """Score how well this resume matches the job description...
Resume data:
{resume_json}
Job description:
{job_description}
Return ONLY valid JSON."""
```

Rules:
- One file per concern (resume parsing, ATS scoring, gap analysis, content optimization)
- Templates are constants, not functions
- Use `str.format()` or f-strings to fill placeholders
- Always request structured output (JSON) from the LLM

## State Model

`ResumeOptimizerState` in `state.py` is the single source of truth:

- **Inputs**: `resume_path`, `job_description_path` (or `job_description_text`)
- **Parsed data**: `resume` (ResumeData), `job_description` (JobDescription)
- **Analysis**: `ats_score` (ATSScore), `gap_analysis` (GapAnalysis)
- **Optimization**: `optimized_resume` (OptimizedResume)
- **Output**: `output_path`, `report`
- **Tracking**: `errors` (list[str])

All sub-models (`ResumeData`, `JobDescription`, `ATSScore`, `GapAnalysis`, `OptimizedResume`) are Pydantic `BaseModel` with typed fields and defaults.

## Configuration

`config.py` uses Pydantic Settings with `.env` file support:

```python
from resume_operator.config import get_settings
settings = get_settings()
```

All configuration comes from environment variables. Never hardcode values.

## Storage

Local JSON files in `data/` (git-ignored). `report_results` node writes `data/results.json` after each run. No database needed for single-user mode.

## Error Handling

- Nodes catch exceptions and record them: `state.errors.append(f"Node failed: {e}")`
- The pipeline continues on failure
- `report_results` includes all errors in the final output
- CLI displays errors in the results table

## Anti-Patterns (Do NOT)

- Put business logic in `main.py` — CLI is thin, delegates to graph
- Use global mutable state — all data flows through `ResumeOptimizerState`
- Make LLM calls directly in nodes — use `tools/llm_provider.py`
- Hardcode prompts in node functions — use `prompts/` templates
- Store API keys in code — use env vars via `config.py`
- Return the full state from nodes — return only changed fields as a dict
- Create deeply nested class hierarchies — keep it flat (functions + Pydantic models)
- Add a database for single-user mode — JSON files are sufficient
- Import from one node into another — nodes are independent; share via state
- Hardcode resume formatting — use configurable templates in `tools/pdf_generator.py`
