# How to Deploy

Guide for running resume-operator in production environments.

## Local Usage

The simplest deployment — run directly on your machine.

```bash
# Install
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your API key

# Run
python -m resume_operator run --resume resume.pdf --job job.txt --output output.pdf
```

Output files are written to `data/` by default.

## Docker

### Build the Image

```bash
docker build -t resume-operator .
```

### Run

```bash
# Pass API key via environment variable
docker run --rm \
  -e OPENAI_API_KEY=sk-your-key \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/input:/app/input \
  resume-operator run \
    --resume /app/input/resume.pdf \
    --job /app/input/job.txt \
    --output /app/data/optimized_resume.pdf
```

### Dockerfile

The project includes a `Dockerfile` at the repo root:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .
ENTRYPOINT ["python", "-m", "resume_operator"]
```

## Docker Compose

For convenience, use `docker-compose.yml`:

```yaml
services:
  resume-operator:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./input:/app/input
    command: run --resume /app/input/resume.pdf --job /app/input/job.txt
```

```bash
# Place your files in ./input/
docker compose run resume-operator
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_PROVIDER` | No | `openai` (default), `anthropic`, `google` |
| `LLM_MODEL` | No | Model name, default `gpt-4o` |
| `OPENAI_API_KEY` | If using OpenAI | Your OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Your Anthropic API key |
| `GOOGLE_API_KEY` | If using Google | Your Google AI API key |
| `LOG_LEVEL` | No | `INFO` (default), `DEBUG`, `WARNING` |

## Security Considerations

- **Never bake API keys into Docker images** — use env vars or `.env` files
- **Never commit `.env`** — it's in `.gitignore`
- **Resume data is personal** — `data/` directory is git-ignored, mount it as a volume in Docker
- **Use `.env` files** with `docker compose` instead of inline `-e` flags for convenience

## Troubleshooting

### "OPENAI_API_KEY not set"

Your API key is missing or empty. Check your `.env` file or environment variables:
```bash
echo $OPENAI_API_KEY  # Should not be empty
```

### "FileNotFoundError: resume.pdf"

The resume file path is incorrect. Verify the file exists:
```bash
ls -la resume.pdf
```
In Docker, make sure the file is mounted into the container.

### "ValueError: Unsupported LLM provider: xxx"

The `LLM_PROVIDER` value must be one of: `openai`, `anthropic`, `google`.

### "PDF has no extractable text"

The PDF is image-based (scanned document). resume-operator requires text-based PDFs. Use OCR software to convert it first.

### "Model not found" or API errors

Check that `LLM_MODEL` matches your provider:
- OpenAI: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`
- Anthropic: `claude-sonnet-4-20250514`, `claude-haiku-4-5-20251001`
- Google: `gemini-2.0-flash`, `gemini-2.5-pro`
