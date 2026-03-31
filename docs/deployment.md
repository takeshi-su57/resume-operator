# Deployment Guide

How to run resume-operator locally, in Docker, or with Docker Compose.

## Local Usage

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
git clone https://github.com/takeshi-su57/resume-operator.git
cd resume-operator
uv sync
```

### Configure

```bash
cp .env.example .env
# Edit .env — set LLM_PROVIDER and the matching API key
```

### Run

```bash
# Full optimization pipeline
uv run resume-operator run --resume resume.pdf --job job.txt

# Quick ATS score only
uv run resume-operator score --resume resume.pdf --job job.txt

# Parse resume only
uv run resume-operator parse-resume --resume resume.pdf

# Validate inputs without executing
uv run resume-operator run --resume resume.pdf --job job.txt --dry-run

# Verbose logging
uv run resume-operator run --resume resume.pdf --job job.txt -v
```

## Docker

### Build

```bash
docker build -t resume-operator .
```

### Run

Pass your API key via environment variable and mount input/output directories:

```bash
docker run --rm \
  -e LLM_PROVIDER=openai \
  -e OPENAI_API_KEY=sk-... \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/data:/app/data \
  resume-operator \
  run --resume /app/input/resume.pdf --job /app/input/job.txt --output /app/data/optimized_resume.pdf
```

### Score only

```bash
docker run --rm \
  -e LLM_PROVIDER=openai \
  -e OPENAI_API_KEY=sk-... \
  -v $(pwd)/input:/app/input \
  resume-operator \
  score --resume /app/input/resume.pdf --job /app/input/job.txt
```

## Docker Compose

### Setup

1. Place your resume PDF and job description in an `input/` directory:

```
input/
  resume.pdf
  job.txt
```

2. Create a `.env` file with your configuration (see `.env.example`).

### Run

```bash
# Full pipeline (default command)
docker compose run --rm resume-operator

# Override command for score only
docker compose run --rm resume-operator score --resume /app/input/resume.pdf --job /app/input/job.txt

# Rebuild after code changes
docker compose build
```

### Output

Results are written to the `data/` directory:

- `data/optimized_resume.pdf` — the optimized resume
- `data/results.json` — JSON report with ATS score, gaps, and changes

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | Yes | `openai` | LLM provider: `openai`, `anthropic`, `google`, `openrouter` |
| `LLM_MODEL` | No | `gpt-4o` | Model name for the selected provider |
| `OPENAI_API_KEY` | If provider=openai | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | If provider=anthropic | — | Anthropic API key |
| `GOOGLE_API_KEY` | If provider=google | — | Google AI API key |
| `OPENROUTER_API_KEY` | If provider=openrouter | — | OpenRouter API key |
| `LOG_LEVEL` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

See [.env.example](../.env.example) for a template.

## Security Considerations

- **Never bake API keys into Docker images.** Pass them via `-e`, `--env-file`, or Docker secrets.
- **Never commit `.env` files.** The `.env` file is in `.gitignore`.
- **Resume data is personal.** The `data/` directory contains resume content and is git-ignored. Do not commit or share output files.
- **Use `LOG_LEVEL=WARNING` in production** to avoid logging sensitive data. `DEBUG` level logs LLM prompts and responses which may contain resume content.

## Troubleshooting

### "API key not set"

```
ValueError: OPENAI_API_KEY not set. Add it to your .env file.
```

**Fix:** Set the API key for your chosen provider in `.env` or pass it via `-e` in Docker.

### "PDF file not found"

```
Error: 'resume.pdf' does not exist or is not a file.
```

**Fix:** Check the file path. In Docker, files must be mounted into the container (e.g., `-v $(pwd)/input:/app/input`).

### "Not a PDF file"

```
Error: 'resume.txt' is not a PDF file (expected .pdf extension).
```

**Fix:** The `--resume` option requires a `.pdf` file. Convert your document to PDF first.

### "Unsupported LLM provider"

```
ValueError: Unsupported LLM provider: gemini
```

**Fix:** Use one of: `openai`, `anthropic`, `google`, `openrouter`. Set `LLM_PROVIDER` in your `.env`.

### "No extractable text found in PDF"

```
ValueError: No extractable text found in PDF: resume.pdf
```

**Fix:** The PDF may be image-based (scanned). resume-operator requires text-based PDFs. Use OCR to convert the PDF first.
