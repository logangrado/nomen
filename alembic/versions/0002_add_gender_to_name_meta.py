"""name_meta: add gender, btn_id, serial PK (multiple entries per name)

Recreates name_meta to support multiple BTN entries per name
(e.g. ada-1, ada-2, ada-3) with a serial PK and btn_id unique constraint.
Also adds gender column (M/F/MF).

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "name_meta",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("btn_id", sa.Text(), nullable=True),
        sa.Column("origin", sa.Text(), nullable=True),
        sa.Column("language_tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("meaning", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "gender",
            sa.Text(),
            sa.CheckConstraint("gender IN ('M','F','MF')"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["name"], ["names.name"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("btn_id", name="name_meta_btn_id_key"),
    )
    op.create_index(
        "ix_name_meta_language_tags", "name_meta", ["language_tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_name_meta_language_tags", table_name="name_meta")
    op.drop_table("name_meta")
