# [Docs]: Write "How to Deploy" guide

## Description

Create a deployment guide covering how to run resume-operator in different environments: local, Docker container, and as an on-demand service. Include a Dockerfile and docker-compose.yml.

## Motivation

Users need clear instructions to deploy the tool beyond their local dev machine. Docker support makes it portable and reproducible across environments.

## Tasks

- [ ] Create `docs/deployment.md`
- [ ] Section: Local usage (pip install, .env setup, CLI commands)
- [ ] Section: Docker (write a `Dockerfile`, document build/run commands, env var passthrough)
- [ ] Section: Docker Compose (with `.env` file mounting)
- [ ] Section: Environment variables reference (link to README table)
- [ ] Section: Security considerations (API key management, never bake keys into images)
- [ ] Section: Troubleshooting (common errors: missing API key, PDF not readable, model not found)
- [ ] Create `Dockerfile` at repo root (Python 3.12-slim, pip install, entrypoint)
- [ ] Create `docker-compose.yml` at repo root

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
