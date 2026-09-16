"""Persistent records for v2 trips, task execution, and immutable versions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for application-side defaults."""
    return datetime.now(timezone.utc)


class Trip(Base):
    """A canonical v2 trip request keyed by an idempotency digest."""

    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    active_version: Mapped[int | None] = mapped_column(Integer)

    tasks: Mapped[list[TripTask]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    versions: Mapped[list[TripVersion]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[TripReview]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )


class TripTask(Base):
    """Durable execution state for one trip planning request."""

    __tablename__ = "trip_tasks"
    __table_args__ = (
        Index("ix_trip_tasks_status_updated_at", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    trace_id: Mapped[str] = mapped_column(
        String(64), default=lambda: f"trace_{uuid4().hex}", nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="Task queued.", nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    review_id: Mapped[str | None] = mapped_column(String(40), index=True)
    review_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    trip: Mapped[Trip] = relationship(back_populates="tasks")
    reviews: Mapped[list[TripReview]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class TripVersion(Base):
    """Immutable planner output. Celery redelivery must not duplicate a version."""

    __tablename__ = "trip_versions"
    __table_args__ = (
        UniqueConstraint("trip_id", "version", name="uq_trip_versions_trip_id_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    planner_engine: Mapped[str] = mapped_column(
        String(32), default="legacy", server_default="legacy", nullable=False
    )
    version_role: Mapped[str] = mapped_column(
        String(32), default="primary", server_default="primary", nullable=False
    )
    schema_version: Mapped[str] = mapped_column(
        String(16), default="legacy", server_default="legacy", nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    native_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    parent_version: Mapped[int | None] = mapped_column(Integer)
    review_id: Mapped[str | None] = mapped_column(String(40), index=True)
    change_reason: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    change_sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), default="unknown", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), default="legacy", nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(80), default="legacy", nullable=False)
    tool_versions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    usage_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="versions")
    source_links: Mapped[list[TripSourceLink]] = relationship(
        back_populates="trip_version",
        cascade="all, delete-orphan",
    )


class TripTelemetryEvent(Base):
    """Sanitized operational event correlated across API, worker, node, and tool."""

    __tablename__ = "trip_telemetry_events"
    __table_args__ = (Index("ix_trip_telemetry_task_created_at", "task_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("trip_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    component: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    node: Mapped[str | None] = mapped_column(String(120))
    tool: Mapped[str | None] = mapped_column(String(120))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_cost_usd: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_hit: Mapped[bool | None] = mapped_column(Boolean)
    model_id: Mapped[str | None] = mapped_column(String(160))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    workflow_version: Mapped[str | None] = mapped_column(String(80))
    tool_version: Mapped[str | None] = mapped_column(String(80))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SourceEvidenceRecord(Base):
    """Deduplicated metadata and claim excerpt for one fetched source."""

    __tablename__ = "source_evidence"
    __table_args__ = (
        Index("ix_source_evidence_source_bucket", "source_bucket"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evidence_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    source_bucket: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(253), default="", nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(16), nullable=False)
    trust_level: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    trip_links: Mapped[list[TripSourceLink]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


class TripSourceLink(Base):
    """Idempotent association between an immutable version and its evidence."""

    __tablename__ = "trip_source_links"
    __table_args__ = (
        UniqueConstraint(
            "trip_version_id",
            "source_id",
            name="uq_trip_source_links_version_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_version_id: Mapped[int] = mapped_column(
        ForeignKey("trip_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("source_evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    trip_version: Mapped[TripVersion] = relationship(back_populates="source_links")
    source: Mapped[SourceEvidenceRecord] = relationship(back_populates="trip_links")


class TripReview(Base):
    """Durable human decision and proposed plan for an interrupted workflow."""

    __tablename__ = "trip_reviews"
    __table_args__ = (
        Index("ix_trip_reviews_trip_status", "trip_id", "status"),
        Index("ix_trip_reviews_task_created_at", "task_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("trip_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_type: Mapped[str] = mapped_column(String(16), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    base_version: Mapped[int | None] = mapped_column(Integer)
    proposed_version: Mapped[int | None] = mapped_column(Integer)
    parent_review_id: Mapped[str | None] = mapped_column(
        ForeignKey("trip_reviews.id", ondelete="SET NULL"), index=True
    )
    decision_action: Mapped[str | None] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    change_request: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    impact_scope: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    refreshed_sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    diff_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    preview_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    native_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    trip: Mapped[Trip] = relationship(back_populates="reviews")
    task: Mapped[TripTask] = relationship(back_populates="reviews")


class UserFeedback(Base):
    """Append-only bounded feedback associated with a durable trip and task."""

    __tablename__ = "user_feedback"
    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="rating_range",
        ),
        Index("ix_user_feedback_trip_created_at", "trip_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("trip_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
