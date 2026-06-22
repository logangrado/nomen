"""Tests for nomen.queries — all run against a real per-test Postgres DB."""
import pytest

from nomen.queries import (
    get_language_tags,
    get_matches,
    get_name_detail,
    get_user_ratings,
    random_name,
    search_names,
    upsert_rating,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed(conn):
    """Insert a small set of names + meta + ratings for testing."""
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO names (name) VALUES (%s) ON CONFLICT DO NOTHING",
            [("ada",), ("boris",), ("zara",), ("milan",)],
        )
        cur.executemany(
            """
            INSERT INTO name_meta (btn_id, name, gender, language_tags, meaning)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (btn_id) DO NOTHING
            """,
            [
                ("ada-1", "ada", "F", ["English", "German"], "Short form of Adelaide."),
                ("boris-1", "boris", "M", ["Russian", "Bulgarian"], "Fighter."),
                ("zara-1", "zara", "F", ["Arabic", "Polish"], "Flower."),
                ("milan-1", "milan", "MF", ["Czech", "Slovak"], "Gracious."),
            ],
        )
    conn.commit()


# ---------------------------------------------------------------------------
# get_language_tags
# ---------------------------------------------------------------------------

def test_get_language_tags_empty(conn):
    tags = get_language_tags(conn)
    assert tags == []


def test_get_language_tags(conn):
    _seed(conn)
    tags = get_language_tags(conn)
    assert "Polish" in tags
    assert "Russian" in tags
    assert tags == sorted(tags)


# ---------------------------------------------------------------------------
# search_names
# ---------------------------------------------------------------------------

def test_search_names_no_filters(conn):
    _seed(conn)
    rows = search_names(conn)
    assert len(rows) == 4
    assert rows[0]["name"] == "ada"  # ordered by name


def test_search_names_gender_F(conn):
    _seed(conn)
    rows = search_names(conn, gender="F")
    names = [r["name"] for r in rows]
    assert "ada" in names   # F
    assert "zara" in names  # F
    assert "milan" in names # MF matches F
    assert "boris" not in names  # M only


def test_search_names_gender_M(conn):
    _seed(conn)
    rows = search_names(conn, gender="M")
    names = [r["name"] for r in rows]
    assert "boris" in names  # M
    assert "milan" in names  # MF matches M
    assert "ada" not in names


def test_search_names_language_tags(conn):
    _seed(conn)
    rows = search_names(conn, language_tags=["Polish"])
    names = [r["name"] for r in rows]
    assert "zara" in names   # has Polish
    assert "ada" not in names


def test_search_names_hide_rated(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "love")
    rows = search_names(conn, hide_rated_by="alice")
    names = [r["name"] for r in rows]
    assert "ada" not in names
    assert "boris" in names


def test_search_names_current_user_rating(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "like")
    rows = search_names(conn, current_user="alice")
    ada_row = next(r for r in rows if r["name"] == "ada")
    assert ada_row["user_rating"] == "like"
    boris_row = next(r for r in rows if r["name"] == "boris")
    assert boris_row["user_rating"] is None


# ---------------------------------------------------------------------------
# random_name
# ---------------------------------------------------------------------------

def test_random_name_returns_something(conn):
    _seed(conn)
    result = random_name(conn)
    assert result is not None
    assert "name" in result


def test_random_name_none_when_all_filtered(conn):
    _seed(conn)
    # All names rated by alice
    for name in ("ada", "boris", "zara", "milan"):
        upsert_rating(conn, name, "alice", "dislike")
    result = random_name(conn, hide_rated_by="alice")
    assert result is None


def test_random_name_gender_filter(conn):
    _seed(conn)
    for _ in range(10):
        result = random_name(conn, gender="M")
        assert result is not None
        assert result["gender"] in ("M", "MF")


# ---------------------------------------------------------------------------
# upsert_rating
# ---------------------------------------------------------------------------

def test_upsert_rating_insert(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "love")
    with conn.cursor() as cur:
        cur.execute("SELECT rating FROM ratings WHERE name='ada' AND user_id='alice'")
        row = cur.fetchone()
    assert row[0] == "love"


def test_upsert_rating_update(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "love")
    upsert_rating(conn, "ada", "alice", "like")  # re-rate
    with conn.cursor() as cur:
        cur.execute("SELECT rating FROM ratings WHERE name='ada' AND user_id='alice'")
        row = cur.fetchone()
    assert row[0] == "like"


# ---------------------------------------------------------------------------
# get_matches
# ---------------------------------------------------------------------------

def test_get_matches_empty(conn):
    _seed(conn)
    assert get_matches(conn, "alice", "bob") == []


def test_get_matches_both_love(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "love")
    upsert_rating(conn, "ada", "bob", "love")
    matches = get_matches(conn, "alice", "bob")
    assert len(matches) == 1
    assert matches[0]["name"] == "ada"
    assert matches[0]["match_rank"] == 1  # love+love


def test_get_matches_love_like(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "love")
    upsert_rating(conn, "ada", "bob", "like")
    matches = get_matches(conn, "alice", "bob")
    assert len(matches) == 1
    assert matches[0]["match_rank"] == 2  # love+like


def test_get_matches_excludes_dislike(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "love")
    upsert_rating(conn, "ada", "bob", "dislike")
    matches = get_matches(conn, "alice", "bob")
    assert matches == []


def test_get_matches_sorted_by_strength(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "like")
    upsert_rating(conn, "ada", "bob", "like")
    upsert_rating(conn, "boris", "alice", "love")
    upsert_rating(conn, "boris", "bob", "love")
    matches = get_matches(conn, "alice", "bob")
    assert len(matches) == 2
    assert matches[0]["name"] == "boris"  # love+love first
    assert matches[1]["name"] == "ada"    # like+like second


# ---------------------------------------------------------------------------
# get_user_ratings
# ---------------------------------------------------------------------------

def test_get_user_ratings(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "love")
    upsert_rating(conn, "boris", "alice", "dislike")
    rows = get_user_ratings(conn, "alice")
    names = [r["name"] for r in rows]
    assert "ada" in names
    assert "boris" in names


def test_get_user_ratings_filtered(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", "love")
    upsert_rating(conn, "boris", "alice", "dislike")
    rows = get_user_ratings(conn, "alice", rating="love")
    assert len(rows) == 1
    assert rows[0]["name"] == "ada"


# ---------------------------------------------------------------------------
# get_name_detail
# ---------------------------------------------------------------------------

def test_get_name_detail_with_meta(conn):
    _seed(conn)
    result = get_name_detail(conn, "ada")
    assert result is not None
    assert result["name"] == "ada"
    assert result["gender"] == "F"
    assert result["meaning"] == "Short form of Adelaide."
    assert "English" in result["language_tags"]


def test_get_name_detail_no_stats(conn):
    # No name_stats rows seeded — peak columns should be None
    _seed(conn)
    result = get_name_detail(conn, "ada")
    assert result["peak_year"] is None
    assert result["peak_count"] is None


def test_get_name_detail_with_stats(conn):
    _seed(conn)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO regions (code, name, country_iso2, region_type) "
            "VALUES ('US', 'United States', 'US', 'country') ON CONFLICT DO NOTHING"
        )
        cur.execute(
            "INSERT INTO name_stats (name, source, year, region_code, gender, count) "
            "VALUES ('ada', 'SSA', 2010, 'US', 'F', 500)"
        )
        cur.execute(
            "INSERT INTO name_stats (name, source, year, region_code, gender, count) "
            "VALUES ('ada', 'SSA', 2015, 'US', 'F', 1200)"
        )
    conn.commit()
    result = get_name_detail(conn, "ada")
    assert result["peak_year"] == 2015
    assert result["peak_count"] == 1200


def test_get_name_detail_nonexistent(conn):
    result = get_name_detail(conn, "zzznobodynamedthis")
    assert result is None


def test_get_name_detail_no_meta(conn):
    # Name exists in names table but has no name_meta row
    with conn.cursor() as cur:
        cur.execute("INSERT INTO names (name) VALUES ('rawname')")
    conn.commit()
    result = get_name_detail(conn, "rawname")
    assert result is not None
    assert result["name"] == "rawname"
    assert result["gender"] is None
    assert result["meaning"] is None
