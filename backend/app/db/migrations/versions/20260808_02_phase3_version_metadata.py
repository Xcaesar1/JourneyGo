"""Add planner comparison metadata to immutable trip versions.

Revision ID: 20260808_02
Revises: 20260807_01
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_02"
down_revision: str | None = "20260807_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add non-breaking metadata and retain all existing version payloads."""
    op.add_column(
        "trip_versions",
        sa.Column("planner_engine", sa.String(length=32), server_default="legacy", nullable=False),
    )
    op.add_column(
        "trip_versions",
        sa.Column("version_role", sa.String(length=32), server_default="primary", nullable=False),
    )
    op.add_column(
        "trip_versions",
        sa.Column("schema_version", sa.String(length=16), server_default="legacy", nullable=False),
    )
    op.add_column("trip_versions", sa.Column("native_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove comparison metadata without modifying legacy payloads."""
    op.drop_column("trip_versions", "native_payload")
    op.drop_column("trip_versions", "schema_version")
    op.drop_column("trip_versions", "version_role")
    op.drop_column("trip_versions", "planner_engine")
