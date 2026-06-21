# Nomen — Architecture

A data-driven baby-name discovery app for two people trying to find names they
both like. Not a swipe app — a *data* app.

## Problem

Two people need to converge on a baby name. Most name tools are either pure vibes
(swipe apps with confetti) or reference-only (look up meanings). What's missing is
a *queryable, filterable database* with real frequency data, so you can answer:

- "Show me girl names popular in Poland in the 1990s but rare in the US"
- "What names peaked between 2005–2015 and are now declining?"
- "Give me Eastern European names with a similar feel to Katerina"

Slavic name coverage is a first-class concern (not an afterthought).

---

## Key Decisions

### Database: PostgreSQL

The deployment target (docker-compose locally → Kubernetes) drives this choice.
DuckDB was initially considered for its OLAP strengths, but is unsuitable here:
it's an embedded/file-based engine — multiple app pods cannot connect to it, and
it has no network listener. That rules it out for any containerised deployment.

PostgreSQL wins:
- Standard `postgres` service in docker-compose; well-supported on Kubernetes
  (CloudNativePG operator or Bitnami Helm chart)
- Proper concurrent access — essential once two users are rating simultaneously
  in Phase 3
- Native `TEXT[]` arrays, `JSONB`, window functions, and `GIN` indexes cover
  everything this app needs
- ~7M rows (full SSA dataset) is trivially small for Postgres
- ETL pipelines can load via `COPY` or `psycopg` bulk insert — fast enough

**Local dev**: `docker-compose.yml` with a `postgres:16` service and a volume
for persistence. The app connects via `DATABASE_URL` env var.

**Kubernetes**: CloudNativePG `Cluster` resource (preferred — handles
failover, backups, connection pooling via PgBouncer). Alternatively Bitnami
`postgresql` Helm chart for a simpler single-instance setup.

### Multi-Country Schema From Day One

The schema is designed to absorb data from any country, not retro-fitted later.
First pipeline is SSA (US), but Eastern European sources (Polish GUS, Czech ČSÚ)
are near-term. Behind the Name covers Slavic etymology.

Names can appear in multiple scripts: `Katerina` (Latin), `Катерина` (Cyrillic),
`Ekaterina` (common romanization) are all the same name. The `name_variants` table
tracks these relationships.

### Ratings: 4-Point Scale Per User

`love / like / dislike / hate` — intentionally graduated so there's signal in the
middle. A **match** is defined as both users rating a name `love` or `like`. Each
user rates independently; the app surfaces matches.

### Schema Migrations: Alembic + SQLAlchemy Core

Alembic is the standard Python migration tool and works well here:
- Tracks applied migrations in a `alembic_version` table in Postgres
- `alembic upgrade head` is idempotent — safe to run on every deploy
- Autogenerates migration diffs from SQLAlchemy Core table definitions
  (`alembic revision --autogenerate`)

We use **SQLAlchemy Core** (not ORM) to define the schema in Python. Core gives
Alembic what it needs for autogeneration while keeping the codebase simple —
no ORM overhead, and pipeline bulk loads still use raw `COPY` or
`psycopg` executemany.

**Local**: `alembic upgrade head` runs after `docker-compose up` (or as a
make target).

**Kubernetes**: migrations run as a `Job` (or init container on the app
`Deployment`) that executes `alembic upgrade head` before app pods start.
This ensures migrations complete before traffic is served.

### Architecture: Data-First, Phased

Build the pipeline before the UI. Do not start Phase 3 before Phase 1 is solid.

---

## Schema

```sql
-- Name is its own identity — no surrogate key needed
CREATE TABLE names (
    name  TEXT PRIMARY KEY   -- lowercase, e.g. "katerina"; display with initcap()
);

-- Script variants and transliterations
CREATE TABLE name_variants (
    id              SERIAL PRIMARY KEY,
    name            TEXT REFERENCES names(name),
    script          TEXT,              -- e.g. "Cyrillic", "Latin"
    variant         TEXT NOT NULL,     -- e.g. "Катерина"
    transliteration TEXT               -- romanized form if variant is non-Latin
);

-- Frequency data per source
CREATE TABLE name_stats (
    id          SERIAL PRIMARY KEY,
    name        TEXT REFERENCES names(name),
    source      TEXT NOT NULL,         -- e.g. "SSA", "GUS_PL"
    year        SMALLINT NOT NULL,
    month       SMALLINT,              -- NULL for annual sources
    region_code TEXT REFERENCES regions(code),
    gender      TEXT CHECK (gender IN ('M','F','N')),
    count       INTEGER NOT NULL,
    rank        INTEGER
);

-- Regions (countries, states, provinces)
CREATE TABLE regions (
    code         TEXT PRIMARY KEY,     -- ISO 3166, e.g. "US-CA", "PL"
    name         TEXT NOT NULL,
    country_iso2 TEXT NOT NULL,
    region_type  TEXT CHECK (region_type IN ('country','state','province'))
);

-- Etymology and meaning from reference sources
CREATE TABLE name_meta (
    name          TEXT PRIMARY KEY REFERENCES names(name),
    origin        TEXT,                -- e.g. "Greek", "Slavic"
    language_tags TEXT[],              -- e.g. '{ru,uk,bg}'
    meaning       TEXT,
    notes         TEXT
);

-- Per-user ratings
CREATE TABLE ratings (
    name       TEXT REFERENCES names(name),
    user_id    TEXT NOT NULL,          -- e.g. "alice", "bob"
    rating     TEXT CHECK (rating IN ('love','like','dislike','hate')),
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (name, user_id)
);

-- Indexes for common query patterns
CREATE INDEX ON name_stats (name, year);
CREATE INDEX ON name_stats (source, year, gender);
CREATE INDEX ON name_stats (region_code, year);
CREATE INDEX ON ratings (user_id);
CREATE INDEX ON name_meta USING GIN (language_tags);
```

---

## Data Sources

| Source | Country | Data | Granularity | Format |
|--------|---------|------|-------------|--------|
| SSA Baby Names | US | Counts by year + gender | Annual + per-state | CSV zip |
| CDC NCHS Natality | US | Birth microdata | Monthly possible | Public use files |
| UK ONS Baby Names | UK | England & Wales counts | Annual | XLS/CSV |
| Australian ABS | AU | Counts by state | Annual | XLS |
| GUS (Poland) | PL | Name counts by year | Annual | XLS/CSV |
| Czech ČSÚ | CZ | Name frequency | Annual | XLS |
| Behind the Name | — | Etymology, Slavic names, gender | Reference | Scrape |
| Wiktionary / Unicode CLDR | — | Transliteration, script info | Reference | Dump |

**First pipeline**: SSA national + state data
(`https://www.ssa.gov/oact/babynames/limits.html`).

**Second priority**: Polish GUS (strong Slavic coverage) + Behind the Name for
etymology.

---

## Repo Structure

```
nomen/
├── src/
│   └── nomen/
│       ├── __init__.py
│       ├── db/
│       │   ├── schema.py     # SQLAlchemy Core table definitions (source of truth)
│       │   └── connection.py # engine / session setup
│       ├── models.py         # Pydantic models
│       ├── queries.py        # named query functions
│       ├── cli.py            # interactive CLI (phase 2)
│       ├── api/              # FastAPI app (phase 3)
│       │   └── main.py
│       └── pipelines/        # ETL, one module per source
│           ├── base.py       # shared download/normalize utilities
│           ├── ssa.py
│           └── gus.py
├── alembic/                  # migration environment (tool config, not package code)
│   ├── env.py                # imports nomen.db.schema for autogenerate
│   ├── script.py.mako
│   └── versions/
├── data/                     # raw downloads — gitignored
│   ├── ssa/
│   ├── ons/
│   └── gus/
├── notebooks/                # EDA + ML exploration (phase 4)
├── docs/
│   └── architecture.md       # this file
├── tests/
├── alembic.ini
├── pyproject.toml
└── README.md
```

---

## Build Phases

**Phase 1 — Data Pipeline**
- `docker-compose.yml` with `postgres:16` service
- SQLAlchemy Core table definitions in `db/schema.py`; Alembic tracks migrations
- `alembic upgrade head` applies schema; subsequent changes go through migrations
- Download SSA zip files (national + state), normalize, bulk-load via `COPY`
- Goal: ~7M rows of US name frequency data in Postgres

**Phase 2 — CLI / Query Layer**
- `nomen/queries.py`: filter by frequency, year, region, gender
- `nomen/cli.py`: interactive REPL — browse, filter, rate names
- Ratings stored in `ratings` table

**Phase 3 — Web UI**
- FastAPI backend (`api/`)
- Minimal frontend — two-user shared session, surface matches
- No swipe animations. A list, a rating interface, and a match view.

**Phase 4 — ML Layer**
- Embed names using character n-grams or phonetic features (Soundex, Metaphone)
- Cluster to find "similar feel" neighborhoods (e.g. names near Katerina)
- Predict partner ratings from one user's existing ratings

---

## Implementation Notes

- **SSA privacy floor**: counts < 5 are suppressed entirely. "Rare" means absent,
  not just small.
- **Name storage**: store lowercase in `names.name`; display with `initcap()` in
  Postgres or `.title()` in Python. Edge cases (MacKenzie, O'Brien) are accepted
  trade-offs for a browsing tool.
- **Name deduplication**: lowercase before insert/lookup. Strip diacritics for
  cross-source matching: `unicodedata.normalize('NFKD', name).encode('ascii', 'ignore')`.
- **Cyrillic names**: store native script as canonical, Latin transliteration in
  `name_variants`. Do not force Cyrillic into ASCII.
- **Re-rating**: `ratings` has `UNIQUE (name_id, user_id)` — use
  `INSERT ... ON CONFLICT (name_id, user_id) DO UPDATE SET rating = EXCLUDED.rating`.
- **Bulk load**: use Postgres `COPY` for pipeline ingest (orders of magnitude
  faster than row-by-row inserts for millions of SSA rows).
- **Connection pooling**: on Kubernetes, put PgBouncer in front of Postgres
  (CloudNativePG bundles this). FastAPI + asyncpg already pools connections, but
  PgBouncer protects against connection storms at the DB level.
- **Kubernetes deployment**: CloudNativePG `Cluster` CRD is preferred over a
  plain StatefulSet — it handles failover, WAL archiving, and scheduled backups
  declaratively.
