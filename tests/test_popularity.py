"""Tests for the popularity pipeline and popularity-based search filters."""
import pytest

from nomen.pipelines.popularity import load_popularity
from nomen.queries import search_names, upsert_rating


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pop_conn(conn, monkeypatch, db_url):
    """Connection with US region + name_stats seeded for popularity tests."""
    monkeypatch.setenv("DATABASE_URL", db_url)

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO regions (code, name, country_iso2, region_type) "
            "VALUES ('US', 'United States', 'US', 'country')"
        )
        cur.executemany(
            "INSERT INTO names (name) VALUES (%s)",
            [("rising",), ("falling",), ("stable",), ("extinct",)],
        )

        # 1,000,000 total births per year → rate per 1,000 = count / 1000
        # rising:  counts climb from 100 to 600 over 2014–2023
        # falling: counts drop from 600 to 100 over 2014–2023
        # stable:  counts flat at 300 over 2014–2023
        # extinct: only has data in 2000–2005 (outside last-5yr window)
        rows = []
        for year in range(2014, 2024):  # 10 years
            i = year - 2014  # 0..9
            rows.append(("rising",  "SSA", year, "US", "M", 100 + i * 50))
            rows.append(("falling", "SSA", year, "US", "M", 600 - i * 50))
            rows.append(("stable",  "SSA", year, "US", "M", 300))
            # total births row (name="_total_" doesn't exist — we insert a
            # large "other" name to make total = 1,000,000 per year)
            rows.append(("extinct", "SSA", year - 20, "US", "M", 500))

        # Insert a high-count name to pad total births to ~1,000,000
        cur.execute("INSERT INTO names (name) VALUES ('padding')")
        for year in range(2014, 2024):
            rows.append(("padding", "SSA", year, "US", "M", 998_800))
        for year in range(1994, 2006):
            rows.append(("padding", "SSA", year, "US", "M", 999_500))

        cur.executemany(
            "INSERT INTO name_stats (name, source, year, region_code, gender, count) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            rows,
        )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# load_popularity
# ---------------------------------------------------------------------------

def test_load_popularity_creates_rows(pop_conn):
    load_popularity()
    with pop_conn.cursor() as cur:
        cur.execute("SELECT name FROM name_popularity")
        names = {r[0] for r in cur.fetchall()}
    # rising, falling, stable (and padding) are active; extinct is excluded
    assert {"rising", "falling", "stable"}.issubset(names)
    assert "extinct" not in names


def test_extinct_name_excluded(pop_conn):
    load_popularity()
    with pop_conn.cursor() as cur:
        cur.execute("SELECT name FROM name_popularity")
        names = {r[0] for r in cur.fetchall()}
    assert "extinct" not in names


def test_trend_5yr_direction(pop_conn):
    load_popularity()
    with pop_conn.cursor() as cur:
        cur.execute(
            "SELECT name, trend_5yr FROM name_popularity "
            "WHERE name IN ('rising', 'falling', 'stable')"
        )
        rows = {r[0]: r[1] for r in cur.fetchall()}

    assert rows["rising"] > 0,  "rising name should have positive trend_5yr"
    assert rows["falling"] < 0, "falling name should have negative trend_5yr"
    # stable may have a tiny floating-point non-zero but close to zero
    assert abs(rows["stable"]) < abs(rows["rising"]), \
        "stable trend should be smaller in magnitude than rising"


def test_peak_year_correct(pop_conn):
    load_popularity()
    with pop_conn.cursor() as cur:
        cur.execute("SELECT peak_year FROM name_popularity WHERE name = 'rising'")
        peak_year = cur.fetchone()[0]
        cur.execute("SELECT peak_year FROM name_popularity WHERE name = 'falling'")
        falling_peak = cur.fetchone()[0]

    assert peak_year == 2023  # rising peaks at last year
    assert falling_peak == 2014  # falling peaks at first year


def test_peak_ratio_5yr_at_peak(pop_conn):
    load_popularity()
    with pop_conn.cursor() as cur:
        cur.execute("SELECT peak_ratio_5yr FROM name_popularity WHERE name = 'rising'")
        ratio = cur.fetchone()[0]
    # peak_ratio_5yr = avg_5yr / peak_rate. For a monotonically rising name,
    # avg of last 5 years (2019–2023) < the single peak year (2023),
    # so ratio < 1 but should be high (> 0.7) since it's near its peak.
    assert 0.7 < ratio < 1.0


def test_peak_ratio_5yr_declining(pop_conn):
    load_popularity()
    with pop_conn.cursor() as cur:
        cur.execute("SELECT peak_ratio_5yr FROM name_popularity WHERE name = 'falling'")
        ratio = cur.fetchone()[0]
    # falling name's recent avg is much less than its peak
    assert ratio < 0.5


def test_popularity_pct_5yr_ordering(pop_conn):
    load_popularity()
    with pop_conn.cursor() as cur:
        cur.execute(
            "SELECT name, popularity_pct_5yr FROM name_popularity "
            "WHERE name IN ('rising', 'falling', 'stable') "
            "ORDER BY popularity_pct_5yr DESC"
        )
        rows = cur.fetchall()

    names_in_order = [r[0] for r in rows]
    # rising (avg_5yr highest) > stable (mid) > falling (lowest avg_5yr)
    assert names_in_order[0] == "rising"
    assert names_in_order[-1] == "falling"


def test_avg_5yr_value(pop_conn):
    """avg_5yr for stable name should be ~0.3 (300/1,000,000 * 1000)."""
    load_popularity()
    with pop_conn.cursor() as cur:
        cur.execute("SELECT avg_5yr FROM name_popularity WHERE name = 'stable'")
        avg = cur.fetchone()[0]
    assert avg == pytest.approx(0.3, abs=0.01)


# ---------------------------------------------------------------------------
# search_names popularity filters
# ---------------------------------------------------------------------------

@pytest.fixture
def search_conn(conn, engine):
    """Connection seeded with name_popularity data for filter tests."""
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO names (name) VALUES (%s)",
            [("common",), ("rare",), ("midrange",), ("trendy",), ("fading",)],
        )
        cur.executemany(
            """
            INSERT INTO name_popularity
                (name, recent_rate, avg_5yr, avg_10yr, avg_20yr,
                 popularity_pct_5yr, peak_rate, peak_year,
                 peak_ratio_5yr, trend_5yr, trend_10yr)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                ("common",   5.0, 5.0, 4.5, 3.0,  95.0, 6.0, 2020, 0.83,  0.05, 0.04),
                ("rare",     0.1, 0.1, 0.1, 0.1,   5.0, 0.2, 2015, 0.50, -0.01, 0.00),
                ("midrange", 1.0, 1.0, 1.0, 0.8,  50.0, 1.2, 2018, 0.83,  0.00, 0.01),
                ("trendy",   2.0, 2.0, 1.0, 0.5,  70.0, 2.0, 2023, 1.00,  0.20, 0.15),
                ("fading",   0.5, 0.5, 1.5, 2.5,  30.0, 3.0, 2010, 0.17, -0.15,-0.10),
            ],
        )
    conn.commit()
    return conn


def test_search_popularity_min(search_conn):
    rows = search_names(search_conn, popularity_min=80.0)
    names = {r["name"] for r in rows}
    assert "common" in names       # pct=95
    assert "midrange" not in names # pct=50
    assert "rare" not in names     # pct=5


def test_search_popularity_max(search_conn):
    rows = search_names(search_conn, popularity_max=20.0)
    names = {r["name"] for r in rows}
    assert "rare" in names        # pct=5
    assert "common" not in names  # pct=95


def test_search_popularity_range(search_conn):
    rows = search_names(search_conn, popularity_min=40.0, popularity_max=75.0)
    names = {r["name"] for r in rows}
    assert "midrange" in names  # pct=50
    assert "trendy" in names    # pct=70
    assert "common" not in names
    assert "rare" not in names


def test_search_trend_rising(search_conn):
    rows = search_names(search_conn, trend="rising")
    names = {r["name"] for r in rows}
    assert "trendy" in names   # trend_5yr=0.20
    assert "common" in names   # trend_5yr=0.05
    assert "fading" not in names  # trend_5yr=-0.15
    assert "rare" not in names    # trend_5yr=-0.01


def test_search_trend_falling(search_conn):
    rows = search_names(search_conn, trend="falling")
    names = {r["name"] for r in rows}
    assert "fading" in names   # trend_5yr=-0.15
    assert "rare" in names     # trend_5yr=-0.01
    assert "trendy" not in names


def test_search_trend_and_popularity_combined(search_conn):
    # Rising AND popular (pct > 60)
    rows = search_names(search_conn, trend="rising", popularity_min=60.0)
    names = {r["name"] for r in rows}
    assert "trendy" in names   # rising + pct=70
    assert "common" in names   # rising + pct=95
    assert "fading" not in names
    assert "midrange" not in names  # stable trend
