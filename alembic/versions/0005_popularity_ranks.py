"""Replace popularity_pct_5yr with rank columns (1yr/5yr/10yr/20yr)

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("name_popularity", "popularity_pct_5yr")
    op.add_column("name_popularity", sa.Column("rank_1yr", sa.Integer(), nullable=True))
    op.add_column("name_popularity", sa.Column("rank_5yr", sa.Integer(), nullable=True))
    op.add_column("name_popularity", sa.Column("rank_10yr", sa.Integer(), nullable=True))
    op.add_column("name_popularity", sa.Column("rank_20yr", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("name_popularity", "rank_20yr")
    op.drop_column("name_popularity", "rank_10yr")
    op.drop_column("name_popularity", "rank_5yr")
    op.drop_column("name_popularity", "rank_1yr")
    op.add_column("name_popularity", sa.Column("popularity_pct_5yr", sa.Float(), nullable=True))
