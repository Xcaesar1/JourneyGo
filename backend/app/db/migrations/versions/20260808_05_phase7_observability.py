"""Add trace correlation, runtime manifests, and sanitized telemetry.

Revision ID: 20260808_05
Revises: 20260808_04
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_05"
down_revision: str | None = "20260808_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trip_tasks", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.execute("UPDATE trip_tasks SET trace_id = 'legacy_' || id WHERE trace_id IS NULL")
    op.alter_column("trip_tasks", "trace_id", nullable=False)
    op.create_index(op.f("ix_trip_tasks_trace_id"), "trip_tasks", ["trace_id"], unique=True)

    op.add_column(
        "trip_versions",
        sa.Column("model_id", sa.String(length=160), server_default="unknown", nullable=False),
    )
    op.add_column(
        "trip_versions",
        sa.Column("prompt_version", sa.String(length=80), server_default="legacy", nullable=False),
    )
    op.add_column(
        "trip_versions",
        sa.Column("workflow_version", sa.String(length=80), server_default="legacy", nullable=False),
    )
    op.add_column("trip_versions", sa.Column("tool_versions", sa.JSON(), nullable=True))
    op.add_column("trip_versions", sa.Column("usage_summary", sa.JSON(), nullable=True))
    op.execute("UPDATE trip_versions SET tool_versions = '{}', usage_summary = '{}'")
    op.alter_column("trip_versions", "tool_versions", nullable=False)
    op.alter_column("trip_versions", "usage_summary", nullable=False)

    op.create_table(
        "trip_telemetry_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=40), nullable=False),
        sa.Column("trip_id", sa.String(length=40), nullable=False),
        sa.Column("component", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("node", sa.String(length=120), nullable=True),
        sa.Column("tool", sa.String(length=120), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("model_cost_usd", sa.Float(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=True),
        sa.Column("model_id", sa.String(length=160), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("workflow_version", sa.String(length=80), nullable=True),
        sa.Column("tool_version", sa.String(length=80), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"], ["trip_tasks.id"], name=op.f("fk_trip_telemetry_events_task_id_trip_tasks"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_trip_telemetry_events_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_telemetry_events")),
    )
    op.create_index(op.f("ix_trip_telemetry_events_trace_id"), "trip_telemetry_events", ["trace_id"])
    op.create_index(op.f("ix_trip_telemetry_events_task_id"), "trip_telemetry_events", ["task_id"])
    op.create_index(
        "ix_trip_telemetry_task_created_at",
        "trip_telemetry_events",
        ["task_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_trip_telemetry_task_created_at", table_name="trip_telemetry_events")
    op.drop_index(op.f("ix_trip_telemetry_events_task_id"), table_name="trip_telemetry_events")
    op.drop_index(op.f("ix_trip_telemetry_events_trace_id"), table_name="trip_telemetry_events")
    op.drop_table("trip_telemetry_events")
    op.drop_column("trip_versions", "usage_summary")
    op.drop_column("trip_versions", "tool_versions")
    op.drop_column("trip_versions", "workflow_version")
    op.drop_column("trip_versions", "prompt_version")
    op.drop_column("trip_versions", "model_id")
    op.drop_index(op.f("ix_trip_tasks_trace_id"), table_name="trip_tasks")
    op.drop_column("trip_tasks", "trace_id")
