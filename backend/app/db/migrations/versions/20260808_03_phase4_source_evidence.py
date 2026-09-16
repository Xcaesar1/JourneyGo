"""Persist source evidence and immutable trip-version links.

Revision ID: 20260808_03
Revises: 20260808_02
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_03"
down_revision: str | None = "20260808_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evidence_key", sa.String(length=64), nullable=False),
        sa.Column("source_bucket", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("claim_type", sa.String(length=64), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_status", sa.String(length=16), nullable=False),
        sa.Column("trust_level", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_evidence")),
        sa.UniqueConstraint("evidence_key", name=op.f("uq_source_evidence_evidence_key")),
    )
    op.create_index(
        "ix_source_evidence_source_bucket",
        "source_evidence",
        ["source_bucket"],
    )
    op.create_table(
        "trip_source_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trip_version_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["source_evidence.id"],
            name=op.f("fk_trip_source_links_source_id_source_evidence"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trip_version_id"],
            ["trip_versions.id"],
            name=op.f("fk_trip_source_links_trip_version_id_trip_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_source_links")),
        sa.UniqueConstraint(
            "trip_version_id",
            "source_id",
            name="uq_trip_source_links_version_source",
        ),
    )
    op.create_index(
        op.f("ix_trip_source_links_source_id"),
        "trip_source_links",
        ["source_id"],
    )
    op.create_index(
        op.f("ix_trip_source_links_trip_version_id"),
        "trip_source_links",
        ["trip_version_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_trip_source_links_trip_version_id"), table_name="trip_source_links")
    op.drop_index(op.f("ix_trip_source_links_source_id"), table_name="trip_source_links")
    op.drop_table("trip_source_links")
    op.drop_index("ix_source_evidence_source_bucket", table_name="source_evidence")
    op.drop_table("source_evidence")
