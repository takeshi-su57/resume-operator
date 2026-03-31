# [Docs]: Write "How to Deploy" guide

## Description

Create a deployment guide covering how to run resume-operator in different environments: local, Docker container, and as an on-demand service. Include a Dockerfile and docker-compose.yml.

## Motivation

Users need clear instructions to deploy the tool beyond their local dev machine. Docker support makes it portable and reproducible across environments.

## Tasks

- [x] Create `docs/deployment.md` with 6 sections
- [x] Section: Local usage (uv install, .env setup, all CLI commands including --dry-run and --verbose)
- [x] Section: Docker (Dockerfile with Python 3.12-slim + uv, layer-cached deps, build/run commands, env var passthrough via `-e`)
- [x] Section: Docker Compose (env_file + volume mounts for input/output, override examples)
- [x] Section: Environment variables reference (full table with 7 vars, link to .env.example)
- [x] Section: Security considerations (4 points: no baked keys, no committed .env, PII handling, log level in prod)
- [x] Section: Troubleshooting (5 common errors: missing API key, file not found, not PDF, bad provider, no text in PDF)
- [x] Create `Dockerfile` at repo root (Python 3.12-slim, uv for deps, layer caching, CLI entrypoint)
- [x] Create `docker-compose.yml` at repo root (env_file, input/data volume mounts)

## Acceptance Criteria

- A user can follow the guide to run resume-operator in Docker
- Dockerfile builds and runs successfully
- No API keys baked into the image
- Troubleshooting section covers top 5 most likely errors

## Key Files

- `docs/deployment.md` (new)
- `Dockerfile` (new)
- `docker-compose.yml` (new)

## Dependencies

- #017

## Labels

`documentation`, `priority:medium`
