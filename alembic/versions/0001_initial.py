"""initial schema: shows, acts, recording_events

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_previous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "acts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("show_id", sa.Integer(), sa.ForeignKey("shows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("act_name", sa.String(), nullable=False),
        sa.Column("scheduled_start", sa.Time(), nullable=True),
        sa.Column("scheduled_end", sa.Time(), nullable=True),
        sa.Column("actual_start", sa.Time(), nullable=True),
        sa.Column("actual_end", sa.Time(), nullable=True),
        sa.Column("screentime_total_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("screentime_session_start", sa.Time(), nullable=True),
        sa.UniqueConstraint("show_id", "row_index", name="uq_act_show_row"),
    )

    op.create_table(
        "recording_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("show_id", sa.Integer(), sa.ForeignKey("shows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("act_id", sa.Integer(), sa.ForeignKey("acts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("fired_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("recording_events")
    op.drop_table("acts")
    op.drop_table("shows")
