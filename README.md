# resume-operator

[![CI](https://github.com/takeshi-su57/resume-operator/actions/workflows/ci.yml/badge.svg)](https://github.com/takeshi-su57/resume-operator/actions/workflows/ci.yml)

Automatically tailors resumes to match job descriptions by highlighting relevant skills and experience while keeping the original profile intact.

## Features

- **`master_resume.yaml`** as hand-maintained source of truth (no LLM for ingestion)
- One-time `bootstrap` command to seed the YAML from an existing PDF
- ATS (Applicant Tracking System) compatibility scoring
- Gap analysis — identifies missing keywords and weak areas
- LLM-powered content optimization tailored to the job
- Optimized resume PDF generation (ReportLab)
- Configurable LLM provider (OpenAI, Anthropic, Google, OpenRouter)
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
├── state.py             # ResumeOptimizerState model (ResumeMaster + legacy ResumeData)
├── graph.py             # LangGraph StateGraph
├── nodes/               # Pipeline steps
│   ├── load_master.py     # Read master_resume.yaml (no LLM)
│   ├── parse_resume.py    # Legacy: LLM-parse a PDF
│   ├── ats_score.py
│   ├── analyze_gaps.py
│   ├── optimize_content.py
│   ├── generate_pdf.py
│   └── report_results.py
├── tools/               # I/O utilities
│   ├── master_resume.py   # YAML load/save + PDF→YAML bootstrap helper
│   ├── pdf_parser.py
│   ├── pdf_generator.py
│   └── llm_provider.py
└── prompts/             # LLM prompt templates
input/
├── master_resume.example.yaml   # Schema example — copy and edit
└── job.txt
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

# One-time: bootstrap master_resume.yaml from your existing PDF
uv run python -m resume_operator bootstrap --resume my-resume.pdf --output data/master_resume.yaml
# Review and hand-edit data/master_resume.yaml

# (Optional) Maintain a facts bank alongside the master for items that didn't fit on the trimmed resume
# see input/facts_bank.example.yaml

# Run the optimizer (preferred: master YAML)
# Each run writes into its own folder under data/applications/{date}_{slug}/
uv run python -m resume_operator run --master data/master_resume.yaml --facts data/facts_bank.yaml --job job_description.txt
# Output: data/applications/2026-04-21_<slug>/{resume.pdf, results.json, tailored.yaml, diff.md}
```

## Commands

| Command | Description |
|---------|-------------|
| `uv run python -m resume_operator run --master <yaml> --job <job> [--style <yaml>]` | Run full pipeline; auto-offers enrichment interview if tailoring is thin; optional style override |
| `uv run python -m resume_operator bootstrap --resume <pdf>` | One-time: PDF → `master_resume.yaml` |
| `uv run python -m resume_operator extract-style --from <docx> --output <yaml>` | Derive a StyleTemplate from a reference `.docx` CV |
| `uv run python -m resume_operator parse-resume` | Parse a resume PDF (legacy, no YAML write) |
| `uv run python -m resume_operator score --master <yaml> --job <job>` | ATS compatibility score only |
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
