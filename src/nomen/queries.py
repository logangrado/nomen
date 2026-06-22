"""Named query functions for the nomen database."""
import psycopg
import psycopg.rows


def get_language_tags(conn: psycopg.Connection) -> list[str]:
    """Return all distinct language tags in name_meta, sorted."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT unnest(language_tags) AS tag FROM name_meta ORDER BY 1"
        )
        return [row[0] for row in cur.fetchall()]



def search_names(
    conn: psycopg.Connection,
    *,
    gender: str | None = None,
    language_tags: list[str] | None = None,
    hide_rated_by: str | None = None,
    current_user: str | None = None,
    search: str | None = None,
    trend: str | None = None,
    sort_by: str = "name",
    sort_dir: str = "asc",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return a page of names matching the given filters.

    Args:
        gender: 'M' or 'F' — matches M/MF or F/MF entries respectively
        language_tags: filter to names where name_meta.language_tags overlaps
        hide_rated_by: user_id — exclude names already rated by this user
        current_user: user_id — include their current rating in results
        search: prefix filter on name (case-insensitive)
        trend: 'rising' (trend_5yr > 0) or 'falling' (trend_5yr < 0)
        sort_by: column to sort by (whitelisted); sort_dir: 'asc' or 'desc'
        limit/offset: pagination
    """
    hide_join = ""
    if hide_rated_by:
        hide_join = (
            "LEFT JOIN ratings r_hide ON r_hide.name = n.name "
            "AND r_hide.user_id = %(hide_rated_by)s"
        )

    rating_join = ""
    if current_user:
        rating_join = (
            "LEFT JOIN ratings r_cur ON r_cur.name = n.name "
            "AND r_cur.user_id = %(current_user)s"
        )

    pop_join = ""
    if trend:
        pop_join = "LEFT JOIN name_popularity np ON np.name = n.name"

    conditions = []
    if gender == "M":
        conditions.append("nm.gender IN ('M', 'MF')")
    elif gender == "F":
        conditions.append("nm.gender IN ('F', 'MF')")
    if language_tags:
        conditions.append("nm.language_tags && %(language_tags)s")
    if hide_rated_by:
        conditions.append("r_hide.rating IS NULL")
    if search:
        conditions.append("n.name LIKE %(search)s")
    if trend == "rising":
        conditions.append("np.trend_5yr > 0")
    elif trend == "falling":
        conditions.append("np.trend_5yr < 0")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    _SORT_COLS = {
        "name":        "n.name",
        "rank_1yr":    "np.rank_1yr",
        "rank_5yr":    "np.rank_5yr",
        "rank_10yr":   "np.rank_10yr",
        "rank_20yr":   "np.rank_20yr",
        "recent_rate": "np.recent_rate",
        "avg_5yr":     "np.avg_5yr",
        "avg_10yr":    "np.avg_10yr",
        "avg_20yr":    "np.avg_20yr",
        "trend_5yr":   "np.trend_5yr",
        "trend_10yr":  "np.trend_10yr",
    }
    col = _SORT_COLS.get(sort_by, "n.name")
    direction = "ASC" if sort_dir != "desc" else "DESC"
    # NULLs at end so names without popularity data don't crowd the top
    null_pos = "NULLS LAST" if direction == "DESC" else "NULLS LAST"
    order_by = f"{col} {direction} {null_pos}, n.name ASC"

    rating_col = "r_cur.rating AS user_rating" if current_user else "NULL::text AS user_rating"

    sql = f"""
        SELECT
            n.name,
            nm.gender,
            nm.meaning,
            nm.language_tags,
            np.recent_rate,
            np.avg_5yr,
            np.avg_10yr,
            np.avg_20yr,
            np.rank_1yr,
            np.rank_5yr,
            np.rank_10yr,
            np.rank_20yr,
            np.trend_5yr,
            np.trend_10yr,
            {rating_col}
        FROM names n
        LEFT JOIN name_meta nm ON nm.name = n.name
        LEFT JOIN name_popularity np ON np.name = n.name
        {hide_join}
        {rating_join}
        {where}
        ORDER BY {order_by}
        LIMIT %(limit)s OFFSET %(offset)s
    """

    params = {
        "limit": limit,
        "offset": offset,
        "language_tags": language_tags,
        "hide_rated_by": hide_rated_by,
        "current_user": current_user,
        "search": f"{search.strip().lower()}%" if search else None,
    }

    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def random_name(
    conn: psycopg.Connection,
    *,
    gender: str | None = None,
    language_tags: list[str] | None = None,
    hide_rated_by: str | None = None,
    current_user: str | None = None,
) -> dict | None:
    """Return a single random name matching filters, or None if none match."""
    hide_join = ""
    if hide_rated_by:
        hide_join = (
            "LEFT JOIN ratings r_hide ON r_hide.name = n.name "
            "AND r_hide.user_id = %(hide_rated_by)s"
        )

    rating_join = ""
    if current_user:
        rating_join = (
            "LEFT JOIN ratings r_cur ON r_cur.name = n.name "
            "AND r_cur.user_id = %(current_user)s"
        )

    conditions = []
    if gender == "M":
        conditions.append("nm.gender IN ('M', 'MF')")
    elif gender == "F":
        conditions.append("nm.gender IN ('F', 'MF')")
    if language_tags:
        conditions.append("nm.language_tags && %(language_tags)s")
    if hide_rated_by:
        conditions.append("r_hide.rating IS NULL")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rating_col = "r_cur.rating AS user_rating" if current_user else "NULL::text AS user_rating"

    sql = f"""
        SELECT
            n.name,
            nm.gender,
            nm.meaning,
            nm.language_tags,
            {rating_col}
        FROM names n
        LEFT JOIN name_meta nm ON nm.name = n.name
        {hide_join}
        {rating_join}
        {where}
        ORDER BY random()
        LIMIT 1
    """

    params = {
        "language_tags": language_tags,
        "hide_rated_by": hide_rated_by,
        "current_user": current_user,
    }

    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def get_name_stats(conn: psycopg.Connection, name: str) -> list[dict]:
    """Return yearly US national rate (per 1,000 same-gender births) for a name."""
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT
                ns.year,
                ns.gender,
                round(ns.count::numeric / totals.total * 1000, 2) AS rate_per_1000
            FROM name_stats ns
            JOIN (
                SELECT year, gender, sum(count) AS total
                FROM name_stats
                WHERE region_code = 'US'
                GROUP BY year, gender
            ) totals ON totals.year = ns.year AND totals.gender = ns.gender
            WHERE ns.name = %s AND ns.region_code = 'US'
            ORDER BY ns.year, ns.gender
            """,
            (name,),
        )
        return cur.fetchall()


def get_name_detail(conn: psycopg.Connection, name: str) -> dict | None:
    """Return full detail for a name: meta + US peak stats."""
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT
                n.name,
                nm.gender,
                nm.meaning,
                nm.language_tags,
                nm.origin,
                nm.btn_id,
                peak.peak_year,
                peak.peak_count
            FROM names n
            LEFT JOIN name_meta nm ON nm.name = n.name
            LEFT JOIN LATERAL (
                SELECT year AS peak_year, count AS peak_count
                FROM name_stats
                WHERE name = n.name AND region_code = 'US'
                ORDER BY count DESC
                LIMIT 1
            ) peak ON true
            WHERE n.name = %s
            """,
            (name,),
        )
        return cur.fetchone()


def upsert_rating(
    conn: psycopg.Connection, name: str, user_id: str, rating: int
) -> None:
    """Insert or update a rating. rating must be 2 (love), 1 (like), -1 (dislike), -2 (definitely not)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ratings (name, user_id, rating)
            VALUES (%s, %s, %s)
            ON CONFLICT (name, user_id) DO UPDATE SET rating = EXCLUDED.rating
            """,
            (name, user_id, rating),
        )
    conn.commit()


def get_matches(
    conn: psycopg.Connection, user1: str, user2: str
) -> list[dict]:
    """Return names where both users rated love or like, sorted by match strength."""
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT
                r1.name,
                nm.gender,
                nm.meaning,
                nm.language_tags,
                r1.rating AS user1_rating,
                r2.rating AS user2_rating,
                CASE
                    WHEN r1.rating = 2 AND r2.rating = 2 THEN 1
                    WHEN r1.rating = 2 OR  r2.rating = 2 THEN 2
                    ELSE 3
                END AS match_rank
            FROM ratings r1
            JOIN ratings r2 ON r2.name = r1.name AND r2.user_id = %s
            LEFT JOIN name_meta nm ON nm.name = r1.name
            WHERE r1.user_id = %s
              AND r1.rating > 0
              AND r2.rating > 0
            ORDER BY match_rank, r1.name
            """,
            (user2, user1),
        )
        return cur.fetchall()


def get_user_ratings(
    conn: psycopg.Connection,
    user_id: str,
    rating: int | None = None,
) -> list[dict]:
    """Return all ratings for a user, optionally filtered to a specific rating value."""
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        if rating:
            cur.execute(
                """
                SELECT r.name, r.rating, nm.gender, nm.meaning, nm.language_tags
                FROM ratings r
                LEFT JOIN name_meta nm ON nm.name = r.name
                WHERE r.user_id = %s AND r.rating = %s
                ORDER BY r.name
                """,
                (user_id, rating),
            )
        else:
            cur.execute(
                """
                SELECT r.name, r.rating, nm.gender, nm.meaning, nm.language_tags
                FROM ratings r
                LEFT JOIN name_meta nm ON nm.name = r.name
                WHERE r.user_id = %s
                ORDER BY r.rating, r.name
                """,
                (user_id,),
            )
        return cur.fetchall()
