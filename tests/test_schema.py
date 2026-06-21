from sqlalchemy import inspect


def test_all_tables_exist(engine):
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    expected = {"names", "name_stats", "name_variants", "name_meta", "regions", "ratings"}
    assert expected.issubset(tables)


def test_name_stats_columns(engine):
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("name_stats")}
    assert {"id", "name", "source", "year", "month", "region_code", "gender", "count", "rank"}.issubset(cols)


def test_ratings_columns(engine):
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("ratings")}
    assert {"name", "user_id", "rating", "created_at"}.issubset(cols)


def test_regions_columns(engine):
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("regions")}
    assert {"code", "name", "country_iso2", "region_type"}.issubset(cols)
