"""Precompute name popularity metrics from name_stats and store in name_popularity.

Metrics (all based on US national data, combined M+F):
  recent_rate       — rate per 1,000 total births in the most recent year
  avg_5yr           — rolling avg of rate over last 5 years
  avg_10yr          — rolling avg of rate over last 10 years
  avg_20yr          — rolling avg of rate over last 20 years
  popularity_pct_5yr — percentile of avg_5yr among names active in last 5 years
  peak_rate         — highest rate ever recorded
  peak_year         — year of peak_rate
  peak_ratio_5yr    — avg_5yr / peak_rate (1.0 = at peak now)
  trend_5yr         — regr_slope(rate, year) over last 5 years
  trend_10yr        — regr_slope(rate, year) over last 10 years
"""

import os

import psycopg

_COMPUTE_SQL = """
WITH

-- Step 1: normalize counts to rate per 1,000 total births per year
totals AS (
    SELECT year, sum(count) AS total_births
    FROM name_stats
    WHERE region_code = 'US'
    GROUP BY year
),
rates AS (
    SELECT
        ns.name,
        ns.year,
        sum(ns.count)::numeric / t.total_births * 1000 AS rate
    FROM name_stats ns
    JOIN totals t ON t.year = ns.year
    WHERE ns.region_code = 'US'
    GROUP BY ns.name, ns.year, t.total_births
),

-- Step 2: window functions over each name's time series
max_year AS (SELECT max(year) AS y FROM rates),
windowed AS (
    SELECT
        r.name,
        r.year,
        r.rate,
        -- rolling averages (ROWS N PRECEDING = N+1 rows including current)
        avg(r.rate) OVER w5  AS avg_5yr,
        avg(r.rate) OVER w10 AS avg_10yr,
        avg(r.rate) OVER w20 AS avg_20yr,
        -- trend: slope of rate vs year over window
        regr_slope(r.rate, r.year) OVER w5  AS trend_5yr,
        regr_slope(r.rate, r.year) OVER w10 AS trend_10yr,
        -- all-time peak
        max(r.rate)  OVER (PARTITION BY r.name) AS peak_rate,
        first_value(r.year) OVER (
            PARTITION BY r.name ORDER BY r.rate DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS peak_year
    FROM rates r
    CROSS JOIN max_year mx
    WINDOW
        w5  AS (PARTITION BY r.name ORDER BY r.year ROWS 4 PRECEDING),
        w10 AS (PARTITION BY r.name ORDER BY r.year ROWS 9 PRECEDING),
        w20 AS (PARTITION BY r.name ORDER BY r.year ROWS 19 PRECEDING)
),

-- Step 3: keep only the most recent year row per name
recent AS (
    SELECT w.*
    FROM windowed w
    JOIN max_year mx ON w.year = mx.y
),

-- Step 4: rank among "common" names (avg_5yr >= 0.1, roughly ≥400 babies/yr
--         nationally). Ranks names we actually care about; obscure one-offs get NULL.
active AS (
    SELECT name FROM recent WHERE avg_5yr > 0
),
common_ranked AS (
    SELECT
        name,
        rank() OVER (ORDER BY rate         DESC NULLS LAST) AS rank_1yr,
        rank() OVER (ORDER BY avg_5yr      DESC NULLS LAST) AS rank_5yr,
        rank() OVER (ORDER BY avg_10yr     DESC NULLS LAST) AS rank_10yr,
        rank() OVER (ORDER BY avg_20yr     DESC NULLS LAST) AS rank_20yr
    FROM recent
    WHERE avg_5yr >= 0.1
),

-- Step 5: assemble final rows; names below the threshold get NULL ranks
ranked AS (
    SELECT
        r.name,
        r.rate                                           AS recent_rate,
        r.avg_5yr,
        r.avg_10yr,
        r.avg_20yr,
        r.peak_rate,
        r.peak_year,
        r.trend_5yr,
        r.trend_10yr,
        CASE WHEN r.peak_rate > 0
             THEN r.avg_5yr / r.peak_rate
             ELSE NULL
        END                                              AS peak_ratio_5yr,
        cr.rank_1yr,
        cr.rank_5yr,
        cr.rank_10yr,
        cr.rank_20yr
    FROM recent r
    LEFT JOIN common_ranked cr ON cr.name = r.name
    WHERE r.name IN (SELECT name FROM active)
)

SELECT
    name,
    recent_rate,
    avg_5yr,
    avg_10yr,
    avg_20yr,
    rank_1yr,
    rank_5yr,
    rank_10yr,
    rank_20yr,
    peak_rate,
    peak_year,
    peak_ratio_5yr,
    trend_5yr,
    trend_10yr
FROM ranked
"""


def load_popularity() -> None:
    """Recompute name_popularity from name_stats and replace the table contents."""
    db_url = os.environ["DATABASE_URL"]
    with psycopg.connect(db_url) as conn:
        print("Computing popularity metrics (this may take a moment)...", flush=True)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM name_popularity")
            cur.execute(f"""
                INSERT INTO name_popularity (
                    name, recent_rate, avg_5yr, avg_10yr, avg_20yr,
                    rank_1yr, rank_5yr, rank_10yr, rank_20yr,
                    peak_rate, peak_year,
                    peak_ratio_5yr, trend_5yr, trend_10yr
                )
                {_COMPUTE_SQL}
            """)
            count = cur.rowcount
        conn.commit()
    print(f"Done. Computed popularity for {count:,} names.")
