import os

from sqlalchemy import create_engine as _create_engine


def _psycopg_url(url: str) -> str:
    """Ensure the URL uses the psycopg (v3) driver dialect."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine():
    url = _psycopg_url(os.environ["DATABASE_URL"])
    return _create_engine(url)
