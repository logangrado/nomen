FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# uv-dynamic-versioning reads the version from git tags, which aren't available
# in a Docker build context. Bypass it with an explicit version.
ARG VERSION=0.0.0
ENV UV_DYNAMIC_VERSIONING_BYPASS=$VERSION

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["nomen", "serve", "--host", "0.0.0.0", "--no-reload"]
