"""add category column to acts and backfill from name inference

Revision ID: 0002_act_category
Revises: 0001_initial
Create Date: 2026-04-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models import infer_category

revision: str = "0002_act_category"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("acts") as batch:
        batch.add_column(sa.Column("category", sa.String(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, act_name FROM acts")).fetchall()
    for row_id, act_name in rows:
        bind.execute(
            sa.text("UPDATE acts SET category=:cat WHERE id=:id"),
            {"cat": infer_category(act_name or ""), "id": row_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("acts") as batch:
        batch.drop_column("category")
