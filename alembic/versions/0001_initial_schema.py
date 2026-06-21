"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "regions",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("country_iso2", sa.Text(), nullable=False),
        sa.Column(
            "region_type",
            sa.Text(),
            sa.CheckConstraint("region_type IN ('country','state','province')"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("code"),
    )

    op.create_table(
        "names",
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )

    op.create_table(
        "name_variants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("script", sa.Text(), nullable=True),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("transliteration", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["name"], ["names.name"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "name_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=True),
        sa.Column("region_code", sa.Text(), nullable=True),
        sa.Column(
            "gender",
            sa.Text(),
            sa.CheckConstraint("gender IN ('M','F','N')"),
            nullable=True,
        ),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["name"], ["names.name"]),
        sa.ForeignKeyConstraint(["region_code"], ["regions.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_name_stats_name_year", "name_stats", ["name", "year"])
    op.create_index(
        "ix_name_stats_source_year_gender",
        "name_stats",
        ["source", "year", "gender"],
    )
    op.create_index(
        "ix_name_stats_region_code_year", "name_stats", ["region_code", "year"]
    )

    op.create_table(
        "name_meta",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=True),
        sa.Column("language_tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("meaning", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["name"], ["names.name"]),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index(
        "ix_name_meta_language_tags",
        "name_meta",
        ["language_tags"],
        postgresql_using="gin",
    )

    op.create_table(
        "ratings",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column(
            "rating",
            sa.Text(),
            sa.CheckConstraint("rating IN ('love','like','dislike','hate')"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["name"], ["names.name"]),
        sa.PrimaryKeyConstraint("name", "user_id"),
    )
    op.create_index("ix_ratings_user_id", "ratings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ratings_user_id", table_name="ratings")
    op.drop_table("ratings")
    op.drop_index("ix_name_meta_language_tags", table_name="name_meta")
    op.drop_table("name_meta")
    op.drop_index("ix_name_stats_region_code_year", table_name="name_stats")
    op.drop_index("ix_name_stats_source_year_gender", table_name="name_stats")
    op.drop_index("ix_name_stats_name_year", table_name="name_stats")
    op.drop_table("name_stats")
    op.drop_table("name_variants")
    op.drop_table("names")
    op.drop_table("regions")
