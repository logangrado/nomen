"""Add name_popularity table for precomputed popularity metrics.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "name_popularity",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("recent_rate", sa.Float(), nullable=True),
        sa.Column("avg_5yr", sa.Float(), nullable=True),
        sa.Column("avg_10yr", sa.Float(), nullable=True),
        sa.Column("avg_20yr", sa.Float(), nullable=True),
        sa.Column("popularity_pct_5yr", sa.Float(), nullable=True),
        sa.Column("peak_rate", sa.Float(), nullable=True),
        sa.Column("peak_year", sa.SmallInteger(), nullable=True),
        sa.Column("peak_ratio_5yr", sa.Float(), nullable=True),
        sa.Column("trend_5yr", sa.Float(), nullable=True),
        sa.Column("trend_10yr", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["name"], ["names.name"]),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("name_popularity")
