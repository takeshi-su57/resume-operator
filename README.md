# resume-operator

Automatically tailors resumes to match job descriptions by highlighting relevant skills and experience while keeping the original profile intact.

## Features

- Resume PDF parsing with structured data extraction (PyMuPDF + LLM)
- ATS (Applicant Tracking System) compatibility scoring
- Gap analysis — identifies missing keywords and weak areas
- LLM-powered content optimization tailored to the job
- Optimized resume PDF generation (ReportLab)
- Configurable LLM provider (OpenAI, Anthropic, Google)
- CLI with progress monitoring (Typer + Rich)
- Results exported to JSON

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Agent Framework | LangGraph (StateGraph) |
| LLM | LangChain (OpenAI / Anthropic / Google) |
| PDF Parsing | PyMuPDF |
| PDF Generation | ReportLab |
| CLI | Typer + Rich |
| Config | Pydantic Settings + python-dotenv |
| Linting | Ruff |
| Type Checking | mypy (strict) |
| Testing | pytest |

## Project Structure

```
src/resume_operator/
├── main.py              # CLI entry point
├── config.py            # Settings (env vars)
├── state.py             # ResumeOptimizerState model
├── graph.py             # LangGraph StateGraph
├── nodes/               # Pipeline steps
│   ├── parse_resume.py
│   ├── ats_score.py
│   ├── analyze_gaps.py
│   ├── optimize_content.py
│   ├── generate_pdf.py
│   └── report_results.py
├── tools/               # I/O utilities
│   ├── pdf_parser.py
│   ├── pdf_generator.py
│   └── llm_provider.py
└── prompts/             # LLM prompt templates
tests/                   # Test suite
data/                    # Runtime output (git-ignored)
docs/                    # Architecture docs + ADRs
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- An LLM API key (OpenAI, Anthropic, or Google)

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd resume-operator
uv sync --dev

# Configure environment
cp .env.example .env
# Edit .env — add your LLM API key

# Run the optimizer
uv run python -m resume_operator run --resume resume.pdf --job job_description.txt
```

## Commands

| Command | Description |
|---------|-------------|
| `uv run python -m resume_operator run` | Run full optimization pipeline |
| `uv run python -m resume_operator parse-resume` | Parse resume only |
| `uv run python -m resume_operator score` | ATS compatibility score only |
| `uv run pytest` | Run tests |
| `uv run ruff check src/ tests/` | Lint |
| `uv run ruff format src/ tests/` | Format |
| `uv run mypy src/` | Type check |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider: `openai`, `anthropic`, `google`, `openrouter` |
| `LLM_MODEL` | `gpt-4o` | Model name (provider-specific) |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `GOOGLE_API_KEY` | — | Google AI API key |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `LOG_LEVEL` | `INFO` | Logging level |

## AI Engineering

This project uses an AI engineering framework for structured development. See [AI_ENGINEERING.md](AI_ENGINEERING.md) for details.
