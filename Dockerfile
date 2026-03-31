FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install production dependencies only
RUN uv sync --no-dev --no-install-project

# Copy source code
COPY src/ src/

# Install the project itself
RUN uv sync --no-dev

# Create data directory for output
RUN mkdir -p /app/data

ENTRYPOINT ["uv", "run", "resume-operator"]
