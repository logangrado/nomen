import click
from dotenv import load_dotenv

load_dotenv()

from nomen.pipelines.btn import load_btn  # noqa: E402
from nomen.pipelines.popularity import load_popularity  # noqa: E402
from nomen.pipelines.ssa import load_ssa  # noqa: E402


@click.group()
def cli():
    """Nomen — baby name data tool."""
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Re-download zip files even if cached.")
def ingest_ssa(force):
    """Download and bulk-load SSA national + state name data into Postgres."""
    load_ssa(force_download=force)


@cli.command()
@click.option("--letters", default=None, help="Subset of letters to scrape, e.g. 'abc'.")
def ingest_btn(letters):
    """Scrape Behind the Name and load etymology/usage data into name_meta."""
    load_btn(letters=letters)


@cli.command()
def compute_popularity():
    """Precompute name popularity metrics from name_stats into name_popularity."""
    load_popularity()


@cli.command()
def init():
    """Run migrations and ingest all data (SSA + BTN + popularity). Safe to re-run."""
    from alembic.config import Config

    from alembic import command as alembic_command

    click.echo("==> Running database migrations...")
    alembic_cfg = Config("alembic.ini")
    alembic_command.upgrade(alembic_cfg, "head")

    click.echo("==> Ingesting SSA data...")
    load_ssa()

    click.echo("==> Ingesting BTN data...")
    load_btn()

    click.echo("==> Computing popularity metrics...")
    load_popularity()

    click.echo("Done.")


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--reload/--no-reload", default=True, show_default=True)
def serve(host, port, reload):
    """Start the Nomen web UI."""
    import uvicorn

    uvicorn.run("nomen.api.main:app", host=host, port=port, reload=reload)
