# Architecture

## System Overview

resume-operator is a LangGraph-based pipeline that loads a hand-maintained master resume (YAML), scores ATS compatibility, analyzes gaps, optimizes content, and generates tailored PDFs. A legacy PDF-first input path is kept for back-compat and bootstrap.

## Agent Flow

```
START
  |
  +--- master_path set? ---+
  |                        |
  | YES                    | NO (legacy)
  v                        v
load_master            parse_resume
  |                        |
  +-----------+------------+
              |
              v
         ats_score          Score resume against job description
              |
              v
       [conditional]        ATS score >= threshold (default 0.9)?
              |         \
              | NO       \ YES
              v            \
         analyze_gaps       \
              |              \
              v               \
       optimize_content        |
              |                |
              v                |
         generate_pdf           |
              |                |
              v                v
         report_results   report_results
              |
              v
             END
```

## Input Contracts

| Contract | CLI flag | Node | Notes |
|----------|----------|------|-------|
| **Master YAML (preferred)** | `--master` | `load_master` | No LLM. Hand-maintained source of truth. |
| **Resume PDF (legacy)** | `--resume` | `parse_resume` | LLM-parsed. Kept for back-compat and `bootstrap`. |
| **Facts bank (optional)** | `--facts` | `load_master` | YAML pool of items beyond the master. `optimize_content` may pull from here. |

Use `resume-operator bootstrap --resume old.pdf --output data/master_resume.yaml` once to seed the YAML from an existing PDF, then maintain the YAML by hand.

If a `--facts <yaml>` path is provided (or `data/facts_bank.yaml` exists), the facts bank is loaded alongside the master and handed to `optimize_content` as a distinct pool the LLM may pull from when a fact strengthens the match for the JD.

## Conditional Routing

After `ats_score`, a routing function checks the score against `ATS_SKIP_THRESHOLD` (configurable, default 0.9):

- **Score >= threshold**: Skip optimization — route directly to `report_results`. The report notes `optimization_skipped: true`.
- **Score < threshold**: Normal path — continue through `analyze_gaps`, `optimize_content`, `generate_pdf`, then `report_results`.

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| CLI | `main.py` | Typer commands: run, score, parse-resume, bootstrap |
| Graph | `graph.py` | LangGraph StateGraph with conditional routing |
| State | `state.py` | Pydantic model flowing through all nodes (`ResumeMaster`, `ResumeData`, `ATSScore`, …) |
| Nodes | `nodes/` | One function per file, returns state delta |
| Tools | `tools/` | I/O utilities (PDF, LLM, YAML, JSON parsing) |
| Prompts | `prompts/` | LLM prompt templates |
| Config | `config.py` | Pydantic Settings from env vars |

## Data Flow

1. **Input**: `master_resume.yaml` (preferred) or resume PDF + job description text
2. **load_master / parse_resume**: Load structured resume data
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
