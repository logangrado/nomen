from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    SmallInteger,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP

metadata = MetaData()

# regions must be defined before name_stats (FK dependency)
regions = Table(
    "regions",
    metadata,
    Column("code", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("country_iso2", Text, nullable=False),
    Column(
        "region_type",
        Text,
        CheckConstraint("region_type IN ('country','state','province')"),
    ),
)

names = Table(
    "names",
    metadata,
    Column("name", Text, primary_key=True),
)

name_variants = Table(
    "name_variants",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", Text, ForeignKey("names.name")),
    Column("script", Text),
    Column("variant", Text, nullable=False),
    Column("transliteration", Text),
)

name_stats = Table(
    "name_stats",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", Text, ForeignKey("names.name")),
    Column("source", Text, nullable=False),
    Column("year", SmallInteger, nullable=False),
    Column("month", SmallInteger),
    Column("region_code", Text, ForeignKey("regions.code")),
    Column("gender", Text, CheckConstraint("gender IN ('M','F','N')")),
    Column("count", Integer, nullable=False),
    Column("rank", Integer),
)

name_meta = Table(
    "name_meta",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", Text, ForeignKey("names.name")),
    Column("btn_id", Text, unique=True),
    Column("origin", Text),
    Column("language_tags", ARRAY(Text)),
    Column("meaning", Text),
    Column("notes", Text),
    Column("gender", Text, CheckConstraint("gender IN ('M','F','MF')")),
)

name_popularity = Table(
    "name_popularity",
    metadata,
    Column("name", Text, ForeignKey("names.name"), primary_key=True),
    Column("recent_rate", Float),
    Column("avg_5yr", Float),
    Column("avg_10yr", Float),
    Column("avg_20yr", Float),
    Column("rank_1yr", Integer),
    Column("rank_5yr", Integer),
    Column("rank_10yr", Integer),
    Column("rank_20yr", Integer),
    Column("peak_rate", Float),
    Column("peak_year", SmallInteger),
    Column("peak_ratio_5yr", Float),
    Column("trend_5yr", Float),
    Column("trend_10yr", Float),
)

ratings = Table(
    "ratings",
    metadata,
    Column("name", Text, ForeignKey("names.name")),
    Column("user_id", Text, nullable=False),
    Column(
        "rating",
        SmallInteger,
        CheckConstraint("rating IN (2, 1, -1, -2)"),
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default="now()",
    ),
    PrimaryKeyConstraint("name", "user_id"),
)

# Indexes for common query patterns
Index("ix_name_stats_name_year", name_stats.c.name, name_stats.c.year)
Index(
    "ix_name_stats_source_year_gender",
    name_stats.c.source,
    name_stats.c.year,
    name_stats.c.gender,
)
Index(
    "ix_name_stats_region_code_year",
    name_stats.c.region_code,
    name_stats.c.year,
)
Index("ix_ratings_user_id", ratings.c.user_id)
Index(
    "ix_name_meta_language_tags",
    name_meta.c.language_tags,
    postgresql_using="gin",
)
