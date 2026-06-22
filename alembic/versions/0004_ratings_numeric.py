"""Convert ratings.rating from TEXT to SMALLINT.

Mapping:
  'love'    →  2
  'like'    →  1
  'dislike' → -1
  'hate'    → -2
  (any unknown value → NULL)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the text check constraint (Postgres auto-names it ratings_rating_check)
    op.execute("ALTER TABLE ratings DROP CONSTRAINT IF EXISTS ratings_rating_check")
    # Convert column in place using USING clause
    op.execute("""
        ALTER TABLE ratings
        ALTER COLUMN rating TYPE SMALLINT
        USING CASE rating
            WHEN 'love'    THEN  2
            WHEN 'like'    THEN  1
            WHEN 'dislike' THEN -1
            WHEN 'hate'    THEN -2
            ELSE NULL
        END
    """)
    op.execute("ALTER TABLE ratings ADD CONSTRAINT ratings_rating_check CHECK (rating IN (2, 1, -1, -2))")


def downgrade() -> None:
    op.execute("ALTER TABLE ratings DROP CONSTRAINT IF EXISTS ratings_rating_check")
    op.execute("""
        ALTER TABLE ratings
        ALTER COLUMN rating TYPE TEXT
        USING CASE rating
            WHEN  2 THEN 'love'
            WHEN  1 THEN 'like'
            WHEN -1 THEN 'dislike'
            WHEN -2 THEN 'hate'
            ELSE NULL
        END
    """)
    op.execute("ALTER TABLE ratings ADD CONSTRAINT ratings_rating_check CHECK (rating IN ('love','like','dislike','hate'))")
