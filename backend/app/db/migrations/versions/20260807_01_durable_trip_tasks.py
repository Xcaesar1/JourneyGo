"""Create durable trip, task, and version tables.

Revision ID: 20260807_01
Revises:
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Phase 2 durable task schema."""
    op.create_table(
        "trips",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trips")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_trips_idempotency_key")),
    )
    op.create_table(
        "trip_tasks",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("trip_id", sa.String(length=40), nullable=False),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_trip_tasks_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_tasks")),
        sa.UniqueConstraint("celery_task_id", name=op.f("uq_trip_tasks_celery_task_id")),
        sa.UniqueConstraint("trip_id", name=op.f("uq_trip_tasks_trip_id")),
    )
    op.create_index(op.f("ix_trip_tasks_status"), "trip_tasks", ["status"], unique=False)
    op.create_index("ix_trip_tasks_status_updated_at", "trip_tasks", ["status", "updated_at"])
    op.create_index(op.f("ix_trip_tasks_trip_id"), "trip_tasks", ["trip_id"], unique=True)
    op.create_table(
        "trip_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trip_id", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_trip_versions_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_versions")),
        sa.UniqueConstraint("trip_id", "version", name="uq_trip_versions_trip_id_version"),
    )
    op.create_index(op.f("ix_trip_versions_trip_id"), "trip_versions", ["trip_id"])


def downgrade() -> None:
    """Drop the Phase 2 durable task schema."""
    op.drop_index(op.f("ix_trip_versions_trip_id"), table_name="trip_versions")
    op.drop_table("trip_versions")
    op.drop_index(op.f("ix_trip_tasks_trip_id"), table_name="trip_tasks")
    op.drop_index("ix_trip_tasks_status_updated_at", table_name="trip_tasks")
    op.drop_index(op.f("ix_trip_tasks_status"), table_name="trip_tasks")
    op.drop_table("trip_tasks")
    op.drop_table("trips")
