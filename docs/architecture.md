# Architecture

## System Overview

resume-operator is a LangGraph-based pipeline that parses resumes, scores ATS compatibility, analyzes gaps, optimizes content, and generates tailored PDFs.

## Agent Flow

```
START
  |
  v
parse_resume       Extract text from PDF, structure via LLM
  |
  v
ats_score           Score resume against job description
  |
  v
[conditional]       ATS score >= threshold (default 0.9)?
  |           \
  | NO         \ YES
  v              \
analyze_gaps      \
  |                \
  v                 \
optimize_content     |
  |                  |
  v                  |
generate_pdf         |
  |                  |
  v                  v
report_results      report_results
  |
  v
END
```

## Conditional Routing

After `ats_score`, a routing function checks the score against `ATS_SKIP_THRESHOLD` (configurable, default 0.9):

- **Score >= threshold**: Skip optimization — route directly to `report_results`. The report notes `optimization_skipped: true`.
- **Score < threshold**: Normal path — continue through `analyze_gaps`, `optimize_content`, `generate_pdf`, then `report_results`.

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| CLI | `main.py` | Typer commands: run, score, parse-resume |
| Graph | `graph.py` | LangGraph StateGraph with conditional routing |
| State | `state.py` | Pydantic model flowing through all nodes |
| Nodes | `nodes/` | One function per file, returns state delta |
| Tools | `tools/` | I/O utilities (PDF, LLM, JSON parsing) |
| Prompts | `prompts/` | LLM prompt templates |
| Config | `config.py` | Pydantic Settings from env vars |

## Data Flow

1. **Input**: Resume PDF path + job description text
2. **parse_resume**: PDF text extraction (PyMuPDF) + LLM structuring
3. **ats_score**: LLM-based ATS compatibility scoring (0.0-1.0)
4. **Routing**: Skip or continue based on score threshold
5. **analyze_gaps**: LLM identifies gaps, strengths, suggestions
6. **optimize_content**: LLM rewrites resume sections
7. **generate_pdf**: ReportLab renders optimized PDF
8. **report_results**: JSON report to `data/results.json`

## Error Handling

- Each node catches exceptions and records them in `state.errors`
- Pipeline continues on failure — downstream nodes check preconditions
- Final report includes all accumulated errors
