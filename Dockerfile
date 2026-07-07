# ProToPro API — production image.
#
# Multi-stage: uv resolves/installs into a self-contained venv in the builder,
# the runtime stage is a plain python-slim image with only that venv. The
# Research Agent spawns its MCP server as `sys.executable -m p2pops.mcp.server`,
# so the installed package (not the source tree) is all the runtime needs.

# ---- builder ----------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Dependency layer first: only re-resolves when the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Project layer: installs p2pops itself (non-editable, so the venv is portable).
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---- runtime ----------------------------------------------------------------
FROM python:3.13-slim-bookworm

RUN groupadd --system app && useradd --system --gid app --create-home appuser

WORKDIR /app
COPY --from=builder --chown=appuser:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# SQLite + LangGraph checkpoints + Chroma live under /app/data (volume-mounted).
# DATA_DIR is set explicitly so the CWD-relative default can never bite here.
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data && chown appuser:app /app/data

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"]

CMD ["uvicorn", "p2pops.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
