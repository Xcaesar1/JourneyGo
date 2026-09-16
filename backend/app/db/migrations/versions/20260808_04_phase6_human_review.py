"""Add durable human review and immutable version lineage.

Revision ID: 20260808_04
Revises: 20260808_03
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_04"
down_revision: str | None = "20260808_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("active_version", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE trips
        SET active_version = (
            SELECT MAX(trip_versions.version)
            FROM trip_versions
            WHERE trip_versions.trip_id = trips.id
              AND trip_versions.version_role = 'primary'
        )
        """
    )
    op.add_column("trip_tasks", sa.Column("review_id", sa.String(length=40), nullable=True))
    op.add_column("trip_tasks", sa.Column("review_payload", sa.JSON(), nullable=True))
    op.create_index(op.f("ix_trip_tasks_review_id"), "trip_tasks", ["review_id"])

    op.add_column("trip_versions", sa.Column("parent_version", sa.Integer(), nullable=True))
    op.add_column("trip_versions", sa.Column("review_id", sa.String(length=40), nullable=True))
    op.add_column(
        "trip_versions",
        sa.Column("change_reason", sa.Text(), server_default="", nullable=False),
    )
    op.add_column("trip_versions", sa.Column("change_sources", sa.JSON(), nullable=True))
    op.add_column("trip_versions", sa.Column("validation_report", sa.JSON(), nullable=True))
    op.create_index(op.f("ix_trip_versions_review_id"), "trip_versions", ["review_id"])

    op.create_table(
        "trip_reviews",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("trip_id", sa.String(length=40), nullable=False),
        sa.Column("task_id", sa.String(length=40), nullable=False),
        sa.Column("workflow_type", sa.String(length=16), nullable=False),
        sa.Column("thread_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=True),
        sa.Column("proposed_version", sa.Integer(), nullable=True),
        sa.Column("parent_review_id", sa.String(length=40), nullable=True),
        sa.Column("decision_action", sa.String(length=16), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("change_request", sa.JSON(), nullable=True),
        sa.Column("impact_scope", sa.JSON(), nullable=True),
        sa.Column("refreshed_sources", sa.JSON(), nullable=True),
        sa.Column("validation_report", sa.JSON(), nullable=True),
        sa.Column("diff_payload", sa.JSON(), nullable=True),
        sa.Column("preview_payload", sa.JSON(), nullable=True),
        sa.Column("native_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_review_id"],
            ["trip_reviews.id"],
            name=op.f("fk_trip_reviews_parent_review_id_trip_reviews"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["trip_tasks.id"],
            name=op.f("fk_trip_reviews_task_id_trip_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trips.id"],
            name=op.f("fk_trip_reviews_trip_id_trips"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_reviews")),
    )
    op.create_index(op.f("ix_trip_reviews_parent_review_id"), "trip_reviews", ["parent_review_id"])
    op.create_index(op.f("ix_trip_reviews_status"), "trip_reviews", ["status"])
    op.create_index(op.f("ix_trip_reviews_task_id"), "trip_reviews", ["task_id"])
    op.create_index(op.f("ix_trip_reviews_thread_id"), "trip_reviews", ["thread_id"])
    op.create_index(op.f("ix_trip_reviews_trip_id"), "trip_reviews", ["trip_id"])
    op.create_index("ix_trip_reviews_task_created_at", "trip_reviews", ["task_id", "created_at"])
    op.create_index("ix_trip_reviews_trip_status", "trip_reviews", ["trip_id", "status"])

    op.execute("UPDATE trip_versions SET change_sources = '[]' WHERE change_sources IS NULL")
    op.execute("UPDATE trip_versions SET validation_report = '{}' WHERE validation_report IS NULL")
    op.alter_column("trip_versions", "change_sources", nullable=False)
    op.alter_column("trip_versions", "validation_report", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_trip_reviews_trip_status", table_name="trip_reviews")
    op.drop_index("ix_trip_reviews_task_created_at", table_name="trip_reviews")
    op.drop_index(op.f("ix_trip_reviews_trip_id"), table_name="trip_reviews")
    op.drop_index(op.f("ix_trip_reviews_task_id"), table_name="trip_reviews")
    op.drop_index(op.f("ix_trip_reviews_thread_id"), table_name="trip_reviews")
    op.drop_index(op.f("ix_trip_reviews_status"), table_name="trip_reviews")
    op.drop_index(op.f("ix_trip_reviews_parent_review_id"), table_name="trip_reviews")
    op.drop_table("trip_reviews")

    op.drop_index(op.f("ix_trip_versions_review_id"), table_name="trip_versions")
    op.drop_column("trip_versions", "validation_report")
    op.drop_column("trip_versions", "change_sources")
    op.drop_column("trip_versions", "change_reason")
    op.drop_column("trip_versions", "review_id")
    op.drop_column("trip_versions", "parent_version")

    op.drop_index(op.f("ix_trip_tasks_review_id"), table_name="trip_tasks")
    op.drop_column("trip_tasks", "review_payload")
    op.drop_column("trip_tasks", "review_id")
    op.drop_column("trips", "active_version")
