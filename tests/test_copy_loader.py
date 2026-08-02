"""Integration tests for the COPY bulk loader and SSA seed functions.

These tests require a live Postgres connection (provided by the `conn` fixture
from conftest.py via pytest-postgresql).
"""

from nomen.pipelines.base import copy_records
from nomen.pipelines.ssa import _seed_regions, _upsert_names


def test_seed_regions_idempotent(conn):
    """_seed_regions should succeed even when called twice."""
    _seed_regions(conn)
    conn.commit()
    _seed_regions(conn)  # second call must not raise
    conn.commit()

    result = list(conn.execute("SELECT code FROM regions WHERE country_iso2 = 'US'"))
    codes = {row[0] for row in result}
    assert "US" in codes
    assert "US-CA" in codes
    assert "US-TX" in codes


def test_upsert_names_idempotent(conn):
    """_upsert_names should succeed even when called twice with the same names."""
    _upsert_names(conn, {"alice", "bob"})
    conn.commit()
    _upsert_names(conn, {"alice", "charlie"})  # alice is a duplicate
    conn.commit()

    result = list(conn.execute("SELECT name FROM names"))
    names = {row[0] for row in result}
    assert {"alice", "bob", "charlie"}.issubset(names)


def test_copy_records_inserts_rows(conn):
    """copy_records should bulk-insert name_stats rows."""
    _seed_regions(conn)
    _upsert_names(conn, {"alice", "bob"})
    conn.commit()

    rows = [
        ("alice", "SSA", 2020, None, "US", "F", 1000, None),
        ("bob", "SSA", 2020, None, "US", "M", 900, None),
    ]
    columns = ["name", "source", "year", "month", "region_code", "gender", "count", "rank"]
    count = copy_records(conn, "name_stats", columns, iter(rows))
    conn.commit()

    assert count == 2
    result = conn.execute("SELECT count(*) FROM name_stats").fetchone()
    assert result[0] == 2


def test_copy_records_returns_count(conn):
    _seed_regions(conn)
    _upsert_names(conn, {"zara"})
    conn.commit()

    rows = [("zara", "SSA", y, None, "US", "F", 100, None) for y in range(2000, 2010)]
    columns = ["name", "source", "year", "month", "region_code", "gender", "count", "rank"]
    count = copy_records(conn, "name_stats", columns, iter(rows))
    conn.commit()

    assert count == 10
