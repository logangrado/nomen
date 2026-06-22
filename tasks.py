"""Invoke task definitions. Run with: inv <task>"""
import os

from invoke import task

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://nomen:nomen@localhost:5432/nomen"
)


@task
def up(c):
    """Start Postgres via docker compose."""
    c.run("docker compose up -d")
    c.run(
        "docker compose exec postgres "
        "bash -c 'until pg_isready -U nomen -d nomen; do sleep 1; done'"
    )


@task
def down(c):
    """Stop docker compose services."""
    c.run("docker compose down")


@task
def reset(c):
    """Destroy and recreate the Postgres volume (WARNING: deletes all data)."""
    c.run("docker compose down -v")
    c.run("docker compose up -d")


@task
def migrate(c):
    """Apply Alembic migrations (alembic upgrade head)."""
    c.run(f"DATABASE_URL={DATABASE_URL} alembic upgrade head")


@task
def migration(c, msg=""):
    """Generate a new Alembic migration from schema changes.

    Usage: inv migration --msg 'add foo column'
    """
    if not msg:
        raise SystemExit("Provide a message: inv migration --msg 'description'")
    c.run(f'DATABASE_URL={DATABASE_URL} alembic revision --autogenerate -m "{msg}"')




@task
def install(c):
    """Install the package and dev dependencies."""
    c.run("uv sync --all-groups")


@task
def test(c):
    """Run the test suite."""
    c.run(f"DATABASE_URL={DATABASE_URL} pytest tests/ -v")


@task
def lint(c):
    """Run ruff linter."""
    c.run("ruff check src/ tests/")


@task
def fmt(c):
    """Auto-format with ruff."""
    c.run("ruff format src/ tests/")


@task
def serve(c):
    """Start the web UI in dev mode (hot reload)."""
    c.run("nomen serve", pty=True)
