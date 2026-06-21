import psycopg
import pytest
from sqlalchemy import create_engine

from nomen.db.schema import metadata


@pytest.fixture
def db_url(postgresql):
    """Per-test URL; pytest-postgresql creates a fresh DB for each test."""
    info = postgresql.info
    return f"postgresql://{info.user}@{info.host}:{info.port}/{info.dbname}"


@pytest.fixture
def engine(db_url):
    """Per-test engine with schema applied to the fresh DB."""
    sa_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    e = create_engine(sa_url)
    metadata.create_all(e)
    return e


@pytest.fixture
def conn(db_url, engine):
    """Per-test psycopg connection."""
    with psycopg.connect(db_url) as c:
        yield c
