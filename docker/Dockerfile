# Use the official uv image to provide the binary
FROM ghcr.io/astral-sh/uv:latest AS uv_bin
FROM python:3.11-slim

# Install system dependencies (keep curl only if you need it for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# 1. Copy the uv binary from the official image
COPY --from=uv_bin /uv /uvx /bin/

# 2. Configure uv behavior
# - UV_LINK_MODE=copy: Prevents issues with Docker's layered filesystem
# - UV_COMPILE_BYTECODE=1: Faster application startup
# - UV_PYTHON_DOWNLOADS=never: Use the system Python we already have
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_HTTP_TIMEOUT=300 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src"

# 3. Install dependencies separately to leverage Docker layer caching
# We copy uv.lock as well to ensure deterministic builds
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# 4. Copy application code and alembic migration files
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./

# 5. Install the project itself (the -e . equivalent)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Default command 
# (No need for 'python -m' if uvicorn is in the .venv/bin/ which is now in PATH)
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]