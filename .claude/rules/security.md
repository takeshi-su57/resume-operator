# Security Rules

## API Keys

- LLM provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`) must come from environment variables
- Use `config.py` (Pydantic Settings) to access all configuration — never read `os.environ` directly
- `.env` is in `.gitignore` — never commit it
- `.env.example` documents all variables without real values — keep it updated

## Personal Data

- Resume data and optimization results are stored locally in `data/` (git-ignored)
- Never commit personal data (resumes, results, credentials) to git
- Never log full resume text or personal details at INFO level — use DEBUG only
- The `data/` directory must be in `.gitignore`
- Generated PDFs are saved to `data/` by default (git-ignored)

## Logging

- Use Python `logging` module with the standard library
- Never log API keys, passwords, or tokens at any level
- Never log full resume text at INFO level
- Safe to log: job description keywords, ATS scores, optimization status, error messages

## What AI Must Never Generate

- Hardcoded API keys, tokens, passwords, or personal data
- `eval()`, `exec()`, or any dynamic code execution
- Disabled security checks or type checking (`# type: ignore` without justification)
- `subprocess.run` with `shell=True` and user-provided input
- Logging of sensitive data (API keys, resume PII at INFO level)
