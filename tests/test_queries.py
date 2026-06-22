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


def _seed_popularity(conn):
    """Add name_popularity rows for ada, boris, zara; milan has no row (NULL)."""
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO name_popularity (name, recent_rate, avg_5yr, avg_10yr, avg_20yr,
                rank_1yr, rank_5yr, rank_10yr, rank_20yr, trend_5yr, trend_10yr,
                peak_rate, peak_year, peak_ratio_5yr)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO NOTHING
            """,
            [
                # name, recent, 5yr, 10yr, 20yr, r1, r5, r10, r20, t5, t10, peak, pk_yr, ratio
                ("ada",   2.5, 2.3, 2.0, 1.8,  1, 1, 1, 1,  0.05, 0.03, 3.0, 2010, 0.77),
                ("boris", 1.0, 0.9, 0.8, 0.7,  3, 3, 3, 3, -0.01,-0.02, 1.5, 2005, 0.60),
                ("zara",  1.8, 1.5, 1.2, 1.0,  2, 2, 2, 2,  0.02, 0.01, 2.0, 2015, 0.75),
                # milan: no row → NULLs in join
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
    upsert_rating(conn, "ada", "alice", 2)
    rows = search_names(conn, hide_rated_by="alice")
    names = [r["name"] for r in rows]
    assert "ada" not in names
    assert "boris" in names


def test_search_names_current_user_rating(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", 1)
    rows = search_names(conn, current_user="alice")
    ada_row = next(r for r in rows if r["name"] == "ada")
    assert ada_row["user_rating"] == 1
    boris_row = next(r for r in rows if r["name"] == "boris")
    assert boris_row["user_rating"] is None


# ---------------------------------------------------------------------------
# search_names — sorting
# ---------------------------------------------------------------------------

def test_sort_default_alphabetical(conn):
    _seed(conn)
    rows = search_names(conn)
    names = [r["name"] for r in rows]
    assert names == sorted(names)


def test_sort_by_rank_5yr_asc(conn):
    _seed(conn)
    _seed_popularity(conn)
    rows = search_names(conn, sort_by="rank_5yr", sort_dir="asc")
    names = [r["name"] for r in rows]
    # ada=rank1, zara=rank2, boris=rank3, milan=NULL (last)
    assert names.index("ada") < names.index("zara") < names.index("boris")
    assert names[-1] == "milan"  # NULL sorts last


def test_sort_by_avg_5yr_desc(conn):
    _seed(conn)
    _seed_popularity(conn)
    rows = search_names(conn, sort_by="avg_5yr", sort_dir="desc")
    names = [r["name"] for r in rows]
    # ada=2.3, zara=1.5, boris=0.9, milan=NULL
    assert names.index("ada") < names.index("zara") < names.index("boris")
    assert names[-1] == "milan"


def test_sort_nulls_last(conn):
    """Names with no popularity data always sort after names that have it."""
    _seed(conn)
    _seed_popularity(conn)
    for sort_col in ("rank_5yr", "avg_5yr", "trend_5yr"):
        for direction in ("asc", "desc"):
            rows = search_names(conn, sort_by=sort_col, sort_dir=direction)
            names = [r["name"] for r in rows]
            assert names[-1] == "milan", f"milan should be last for {sort_col} {direction}"


def test_sort_unknown_col_falls_back_to_name(conn):
    """Unknown sort_by values should fall back to alphabetical, not error."""
    _seed(conn)
    rows = search_names(conn, sort_by="'; DROP TABLE names; --", sort_dir="asc")
    names = [r["name"] for r in rows]
    assert names == sorted(names)


def test_sort_name_desc(conn):
    _seed(conn)
    rows = search_names(conn, sort_by="name", sort_dir="desc")
    names = [r["name"] for r in rows]
    assert names == sorted(names, reverse=True)


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
        upsert_rating(conn, name, "alice", -1)
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
    upsert_rating(conn, "ada", "alice", 2)
    with conn.cursor() as cur:
        cur.execute("SELECT rating FROM ratings WHERE name='ada' AND user_id='alice'")
        row = cur.fetchone()
    assert row[0] == 2


def test_upsert_rating_update(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", 2)
    upsert_rating(conn, "ada", "alice", 1)  # re-rate
    with conn.cursor() as cur:
        cur.execute("SELECT rating FROM ratings WHERE name='ada' AND user_id='alice'")
        row = cur.fetchone()
    assert row[0] == 1


# ---------------------------------------------------------------------------
# get_matches
# ---------------------------------------------------------------------------

def test_get_matches_empty(conn):
    _seed(conn)
    assert get_matches(conn, "alice", "bob") == []


def test_get_matches_both_love(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", 2)
    upsert_rating(conn, "ada", "bob", 2)
    matches = get_matches(conn, "alice", "bob")
    assert len(matches) == 1
    assert matches[0]["name"] == "ada"
    assert matches[0]["match_rank"] == 1  # love+love


def test_get_matches_love_like(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", 2)
    upsert_rating(conn, "ada", "bob", 1)
    matches = get_matches(conn, "alice", "bob")
    assert len(matches) == 1
    assert matches[0]["match_rank"] == 2  # love+like


def test_get_matches_excludes_dislike(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", 2)
    upsert_rating(conn, "ada", "bob", -1)
    matches = get_matches(conn, "alice", "bob")
    assert matches == []


def test_get_matches_sorted_by_strength(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", 1)
    upsert_rating(conn, "ada", "bob", 1)
    upsert_rating(conn, "boris", "alice", 2)
    upsert_rating(conn, "boris", "bob", 2)
    matches = get_matches(conn, "alice", "bob")
    assert len(matches) == 2
    assert matches[0]["name"] == "boris"  # love+love first
    assert matches[1]["name"] == "ada"    # like+like second


# ---------------------------------------------------------------------------
# get_user_ratings
# ---------------------------------------------------------------------------

def test_get_user_ratings(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", 2)
    upsert_rating(conn, "boris", "alice", -1)
    rows = get_user_ratings(conn, "alice")
    names = [r["name"] for r in rows]
    assert "ada" in names
    assert "boris" in names


def test_get_user_ratings_filtered(conn):
    _seed(conn)
    upsert_rating(conn, "ada", "alice", 2)
    upsert_rating(conn, "boris", "alice", -1)
    rows = get_user_ratings(conn, "alice", rating=2)
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


# ---------------------------------------------------------------------------
# search_names — advanced conditions
# ---------------------------------------------------------------------------

def test_conditions_numeric_lte(conn):
    _seed(conn)
    _seed_popularity(conn)
    # avg_5yr: ada=2.3, zara=1.5, boris=0.9; milan=NULL
    conds = [{"field": "avg_5yr", "op": "lte", "val": "1.5"}]
    rows = search_names(conn, conditions_arg=conds)
    names = [r["name"] for r in rows]
    assert "zara" in names    # 1.5 <= 1.5
    assert "boris" in names   # 0.9 <= 1.5
    assert "ada" not in names # 2.3 > 1.5
    assert "milan" not in names  # NULL excluded


def test_conditions_numeric_gte(conn):
    _seed(conn)
    _seed_popularity(conn)
    conds = [{"field": "avg_5yr", "op": "gte", "val": "1.5"}]
    rows = search_names(conn, conditions_arg=conds)
    names = [r["name"] for r in rows]
    assert "ada" in names
    assert "zara" in names
    assert "boris" not in names
    assert "milan" not in names


def test_conditions_integer_rank(conn):
    _seed(conn)
    _seed_popularity(conn)
    # rank_5yr: ada=1, zara=2, boris=3
    conds = [{"field": "rank_5yr", "op": "lte", "val": "2"}]
    rows = search_names(conn, conditions_arg=conds)
    names = [r["name"] for r in rows]
    assert "ada" in names
    assert "zara" in names
    assert "boris" not in names
    assert "milan" not in names


def test_conditions_combined(conn):
    """Multiple conditions are ANDed together."""
    _seed(conn)
    _seed_popularity(conn)
    # avg_5yr >= 1.0 AND rank_5yr <= 2
    conds = [
        {"field": "avg_5yr", "op": "gte", "val": "1.0"},
        {"field": "rank_5yr", "op": "lte", "val": "2"},
    ]
    rows = search_names(conn, conditions_arg=conds)
    names = [r["name"] for r in rows]
    assert "ada" in names    # 2.3 >= 1.0 AND rank=1
    assert "zara" in names   # 1.5 >= 1.0 AND rank=2
    assert "boris" not in names  # rank=3 fails second condition
    assert "milan" not in names


def test_conditions_gender(conn):
    _seed(conn)
    conds = [{"field": "gender", "op": "", "val": "F"}]
    rows = search_names(conn, conditions_arg=conds)
    names = [r["name"] for r in rows]
    assert "ada" in names
    assert "zara" in names
    assert "milan" in names   # MF matches F
    assert "boris" not in names


def test_conditions_language(conn):
    _seed(conn)
    conds = [{"field": "language", "op": "", "val": "Polish"}]
    rows = search_names(conn, conditions_arg=conds)
    names = [r["name"] for r in rows]
    assert "zara" in names    # has Polish
    assert "ada" not in names  # German, English only


def test_conditions_invalid_field_ignored(conn):
    """Unknown fields are silently skipped — no SQL error."""
    _seed(conn)
    conds = [{"field": "nonexistent", "op": "eq", "val": "100"}]
    rows = search_names(conn, conditions_arg=conds)
    assert len(rows) == 4  # all names returned, invalid condition skipped


def test_conditions_invalid_op_ignored(conn):
    """Unknown operators are silently skipped."""
    _seed(conn)
    _seed_popularity(conn)
    conds = [{"field": "avg_5yr", "op": "INJECTION", "val": "1.0"}]
    rows = search_names(conn, conditions_arg=conds)
    assert len(rows) == 4


def test_conditions_non_numeric_val_ignored(conn):
    """Non-numeric value for numeric field is silently skipped."""
    _seed(conn)
    _seed_popularity(conn)
    conds = [{"field": "avg_5yr", "op": "gte", "val": "not-a-number"}]
    rows = search_names(conn, conditions_arg=conds)
    assert len(rows) == 4  # condition skipped, all names returned


def test_conditions_trend(conn):
    _seed(conn)
    _seed_popularity(conn)
    # trend_5yr: ada=+0.05 (rising), boris=-0.01 (falling), zara=+0.02 (rising)
    conds = [{"field": "trend", "op": "", "val": "rising"}]
    rows = search_names(conn, conditions_arg=conds)
    names = [r["name"] for r in rows]
    assert "ada" in names
    assert "zara" in names
    assert "boris" not in names
    assert "milan" not in names  # NULL trend


def test_conditions_combined_with_gender_filter(conn):
    """conditions_arg works alongside the regular gender parameter."""
    _seed(conn)
    _seed_popularity(conn)
    conds = [{"field": "avg_5yr", "op": "gte", "val": "1.5"}]
    rows = search_names(conn, gender="F", conditions_arg=conds)
    names = [r["name"] for r in rows]
    assert "ada" in names    # F, avg_5yr=2.3
    assert "zara" in names   # F, avg_5yr=1.5
    assert "boris" not in names  # M, avg_5yr=0.9
    assert "milan" not in names  # MF passes gender but avg_5yr=NULL
