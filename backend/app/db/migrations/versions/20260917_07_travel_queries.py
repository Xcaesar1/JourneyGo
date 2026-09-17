"""Add durable travel intents and input pauses without changing historical data."""

import sqlalchemy as sa
from alembic import op

revision = "20260917_07"
down_revision = "20260809_06"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("trip_tasks", sa.Column("pending_input", sa.JSON(), nullable=True))
    op.create_table(
        "travel_queries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("trip_id", sa.String(40), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("authorization", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_travel_queries_trip_id", "travel_queries", ["trip_id"])


def downgrade():
    raise RuntimeError(
        "Preserve travel query evidence. Roll back the feature flag/application, not this migration."
    )
