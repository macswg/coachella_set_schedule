"""add app_settings key/value table

Revision ID: 0003_app_settings
Revises: 0002_act_category
Create Date: 2026-04-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_app_settings"
down_revision: Union[str, None] = "0002_act_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
