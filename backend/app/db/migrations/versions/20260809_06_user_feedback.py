"""Add durable bounded user feedback.

Revision ID: 20260809_06
Revises: 20260808_05
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_06"
down_revision: str | None = "20260808_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("trip_id", sa.String(length=40), nullable=False),
        sa.Column("task_id", sa.String(length=40), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name=op.f("ck_user_feedback_rating_range"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["trip_tasks.id"],
            name=op.f("fk_user_feedback_task_id_trip_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trips.id"],
            name=op.f("fk_user_feedback_trip_id_trips"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_feedback")),
    )
    op.create_index(op.f("ix_user_feedback_task_id"), "user_feedback", ["task_id"])
    op.create_index(op.f("ix_user_feedback_trip_id"), "user_feedback", ["trip_id"])
    op.create_index(
        "ix_user_feedback_trip_created_at",
        "user_feedback",
        ["trip_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_feedback_trip_created_at", table_name="user_feedback")
    op.drop_index(op.f("ix_user_feedback_trip_id"), table_name="user_feedback")
    op.drop_index(op.f("ix_user_feedback_task_id"), table_name="user_feedback")
    op.drop_table("user_feedback")
