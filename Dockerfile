FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["nomen", "serve", "--host", "0.0.0.0", "--no-reload"]
