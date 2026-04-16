# Multi-stage build keeps the final image small (~150MB).
# Stage 1: install dependencies with uv into a shared virtualenv.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install deps first for better Docker layer caching — only reruns when
# pyproject.toml / uv.lock actually change.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-editable

COPY . /app
RUN uv sync --locked --no-editable

# Stage 2: runtime image — just Python + the built virtualenv + app code.
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

# Cloud Run provides $PORT at runtime — the shell expands it here.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
