"""Transactional persistence operations for durable trip tasks."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.feedback_models import TripFeedbackRequestV2
from ..domain.research_models import SourceEvidence
from ..domain.review_models import TripReviewDecisionV2
from .models import (
    SourceEvidenceRecord,
    Trip,
    TripReview,
    TripSourceLink,
    TripTask,
    TripTelemetryEvent,
    TripVersion,
    UserFeedback,
)

FINAL_TASK_STATUSES = frozenset({"completed", "rejected", "failed", "cancelled"})


class IdempotencyConflictError(ValueError):
    """Raised when one idempotency key is reused for a different request."""


def create_or_get_task(
    session: Session,
    *,
    request_payload: dict[str, Any],
    idempotency_key: str,
    max_attempts: int = 3,
    trace_id: str | None = None,
) -> tuple[TripTask, bool]:
    """Create a trip and task atomically, or return the idempotent existing task."""
    existing_trip = session.scalar(select(Trip).where(Trip.idempotency_key == idempotency_key))
    if existing_trip is not None:
        _ensure_same_idempotent_request(existing_trip, request_payload)
        return _task_for_trip(session, existing_trip.id), False

    trip = Trip(
        id=f"trip_{uuid4().hex[:20]}",
        idempotency_key=idempotency_key,
        request_payload=request_payload,
    )
    task = TripTask(
        id=f"task_{uuid4().hex[:20]}",
        trip=trip,
        trace_id=trace_id or f"trace_{uuid4().hex}",
        status="queued",
        stage="queued",
        progress=0,
        message="Task queued for durable execution.",
        max_attempts=max_attempts,
    )
    session.add(task)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        concurrent_trip = session.scalar(select(Trip).where(Trip.idempotency_key == idempotency_key))
        if concurrent_trip is None:
            raise
        _ensure_same_idempotent_request(concurrent_trip, request_payload)
        return _task_for_trip(session, concurrent_trip.id), False
    session.refresh(task)
    return task, True


def get_task(session: Session, task_id: str, *, for_update: bool = False) -> TripTask | None:
    """Load a task, optionally locking it for a state transition."""
    statement = select(TripTask).where(TripTask.id == task_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def get_trip(session: Session, trip_id: str) -> Trip | None:
    """Load a trip request by its durable identifier."""
    return session.get(Trip, trip_id)


def get_task_for_trip(
    session: Session,
    trip_id: str,
    *,
    for_update: bool = False,
) -> TripTask | None:
    """Load the single durable task associated with a canonical trip."""
    statement = select(TripTask).where(TripTask.trip_id == trip_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def create_trip_feedback(
    session: Session,
    *,
    trip_id: str,
    task_id: str,
    feedback: TripFeedbackRequestV2,
) -> UserFeedback:
    """Append bounded feedback without changing task or version state."""
    record = UserFeedback(
        id=f"feedback_{uuid4().hex[:20]}",
        trip_id=trip_id,
        task_id=task_id,
        rating=feedback.rating,
        category=feedback.category,
        comment=feedback.comment,
        version=feedback.version,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def attach_celery_task(
    session: Session,
    task_id: str,
    celery_task_id: str,
    *,
    expected_celery_task_id: str | None = None,
) -> TripTask:
    """Persist the broker task identifier after successful dispatch."""
    task = _required_task(session, task_id, for_update=True)
    if expected_celery_task_id is not None:
        if task.celery_task_id != expected_celery_task_id:
            raise RuntimeError(f"Task {task_id} recovery claim changed before broker confirmation.")
        task.celery_task_id = celery_task_id
        session.commit()
        session.refresh(task)
    elif task.celery_task_id is None:
        task.celery_task_id = celery_task_id
        session.commit()
        session.refresh(task)
    return task


def update_task_state(
    session: Session,
    task_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    result_payload: dict[str, Any] | None = None,
    increment_attempt: bool = False,
    finished: bool = False,
) -> TripTask:
    """Apply one locked task transition and commit it."""
    task = _required_task(session, task_id, for_update=True)
    if status is not None:
        task.status = status
    if stage is not None:
        task.stage = stage
    if progress is not None:
        task.progress = min(100, max(0, progress))
    if message is not None:
        task.message = message
    if error_code is not None:
        task.error_code = error_code
    if error_message is not None:
        task.error_message = error_message
    if result_payload is not None:
        task.result_payload = result_payload
    if increment_attempt:
        task.attempt_count += 1
        task.started_at = task.started_at or datetime.now(timezone.utc)
    if finished:
        task.finished_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(task)
    return task


def request_cancellation(session: Session, task_id: str) -> TripTask:
    """Persist a cooperative cancellation request."""
    task = _required_task(session, task_id, for_update=True)
    if task.status not in FINAL_TASK_STATUSES:
        task.cancel_requested = True
        if task.status in {"queued", "retrying"}:
            task.status = "cancelled"
            task.stage = "cancelled"
            task.message = "Task cancelled before execution."
            task.finished_at = datetime.now(timezone.utc)
        else:
            task.status = "cancel_requested"
            task.stage = "cancel_requested"
            task.message = "Cancellation requested."
        session.commit()
        session.refresh(task)
    return task


def prepare_retry(session: Session, task_id: str) -> TripTask:
    """Reset a failed or cancelled task for an explicit retry."""
    task = _required_task(session, task_id, for_update=True)
    if task.status not in {"failed", "cancelled"}:
        raise ValueError("Only failed or cancelled tasks can be retried.")
    task.status = "queued"
    task.stage = "queued"
    task.progress = 0
    task.message = "Task queued for retry."
    task.error_code = None
    task.error_message = None
    task.cancel_requested = False
    task.celery_task_id = None
    task.attempt_count = 0
    task.finished_at = None
    session.commit()
    session.refresh(task)
    return task


def save_trip_version(
    session: Session,
    *,
    trip_id: str,
    version: int,
    payload: dict[str, Any],
    planner_engine: str = "legacy",
    version_role: str = "primary",
    schema_version: str = "legacy",
    native_payload: dict[str, Any] | None = None,
    source_evidence: Sequence[SourceEvidence] = (),
    parent_version: int | None = None,
    review_id: str | None = None,
    change_reason: str = "",
    change_sources: Sequence[str] = (),
    validation_report: dict[str, Any] | None = None,
    model_id: str = "unknown",
    prompt_version: str = "legacy",
    workflow_version: str = "legacy",
    tool_versions: dict[str, str] | None = None,
    usage_summary: dict[str, Any] | None = None,
    activate: bool = False,
) -> TripVersion:
    """Insert one immutable version, returning the existing row on redelivery."""
    existing = session.scalar(
        select(TripVersion).where(
            TripVersion.trip_id == trip_id,
            TripVersion.version == version,
        )
    )
    if existing is not None:
        _save_source_links(session, existing, source_evidence)
        if activate:
            trip = session.get(Trip, trip_id)
            if trip is not None:
                trip.active_version = existing.version
        session.commit()
        return existing

    record = TripVersion(
        trip_id=trip_id,
        version=version,
        planner_engine=planner_engine,
        version_role=version_role,
        schema_version=schema_version,
        payload=payload,
        native_payload=native_payload,
        parent_version=parent_version,
        review_id=review_id,
        change_reason=change_reason,
        change_sources=list(change_sources),
        validation_report=validation_report or {},
        model_id=model_id,
        prompt_version=prompt_version,
        workflow_version=workflow_version,
        tool_versions=tool_versions or {},
        usage_summary=usage_summary or {},
    )
    session.add(record)
    try:
        session.flush()
        _save_source_links(session, record, source_evidence)
        if activate:
            trip = session.get(Trip, trip_id)
            if trip is None:
                raise LookupError(trip_id)
            trip.active_version = version
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(TripVersion).where(
                TripVersion.trip_id == trip_id,
                TripVersion.version == version,
            )
        )
        if existing is None:
            raise
        return existing
    session.refresh(record)
    return record


def record_telemetry_event(
    session: Session,
    *,
    trace_id: str,
    task_id: str,
    trip_id: str,
    component: str,
    operation: str,
    status: str,
    node: str | None = None,
    tool: str | None = None,
    latency_ms: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    model_cost_usd: float = 0,
    retry_count: int = 0,
    cache_hit: bool | None = None,
    model_id: str | None = None,
    prompt_version: str | None = None,
    workflow_version: str | None = None,
    tool_version: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TripTelemetryEvent:
    """Persist one sanitized event; callers must not pass prompts or result payloads."""
    record = TripTelemetryEvent(
        trace_id=trace_id,
        task_id=task_id,
        trip_id=trip_id,
        component=component,
        operation=operation,
        status=status,
        node=node,
        tool=tool,
        latency_ms=max(0, latency_ms),
        input_tokens=max(0, input_tokens),
        output_tokens=max(0, output_tokens),
        total_tokens=max(0, total_tokens),
        model_cost_usd=max(0, model_cost_usd),
        retry_count=max(0, retry_count),
        cache_hit=cache_hit,
        model_id=model_id,
        prompt_version=prompt_version,
        workflow_version=workflow_version,
        tool_version=tool_version,
        event_metadata=metadata or {},
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_task_telemetry(session: Session, task_id: str) -> list[TripTelemetryEvent]:
    """Return ordered events for one task, bounded to prevent unbounded API responses."""
    return list(
        session.scalars(
            select(TripTelemetryEvent)
            .where(TripTelemetryEvent.task_id == task_id)
            .order_by(TripTelemetryEvent.created_at, TripTelemetryEvent.id)
            .limit(1000)
        )
    )


def _save_source_links(
    session: Session,
    version: TripVersion,
    evidence_items: Sequence[SourceEvidence],
) -> None:
    for evidence in evidence_items:
        source_bucket = _source_bucket(evidence)
        evidence_key = _evidence_key(evidence, source_bucket)
        source = session.scalar(
            select(SourceEvidenceRecord).where(
                SourceEvidenceRecord.evidence_key == evidence_key
            )
        )
        if source is None:
            source = SourceEvidenceRecord(
                id=str(evidence.id),
                evidence_key=evidence_key,
                source_bucket=source_bucket,
                title=evidence.title,
                url=str(evidence.url) if evidence.url is not None else None,
                domain=evidence.domain,
                provider=evidence.provider,
                claim_type=evidence.claim_type,
                claim_text=evidence.claim_text,
                published_at=evidence.published_at,
                fetched_at=evidence.fetched_at,
                freshness_status=evidence.freshness_status,
                trust_level=evidence.trust_level,
                confidence=evidence.confidence,
            )
            session.add(source)
            session.flush()

        linked = session.scalar(
            select(TripSourceLink).where(
                TripSourceLink.trip_version_id == version.id,
                TripSourceLink.source_id == source.id,
            )
        )
        if linked is None:
            session.add(TripSourceLink(trip_version_id=version.id, source_id=source.id))


def _source_bucket(evidence: SourceEvidence) -> str:
    if evidence.url is None:
        return hashlib.sha256(f"unknown:{evidence.id}".encode()).hexdigest()
    fetched_at = evidence.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    bucket = fetched_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
    return hashlib.sha256(f"{evidence.url}\x1f{bucket}".encode()).hexdigest()


def _evidence_key(evidence: SourceEvidence, source_bucket: str) -> str:
    material = f"{source_bucket}\x1f{evidence.claim_type}\x1f{evidence.claim_text}"
    return hashlib.sha256(material.encode()).hexdigest()


def get_trip_version(session: Session, trip_id: str, version: int) -> TripVersion | None:
    """Load an immutable trip version by its business key."""
    return session.scalar(
        select(TripVersion).where(
            TripVersion.trip_id == trip_id,
            TripVersion.version == version,
        )
    )


def list_trip_versions(session: Session, trip_id: str) -> list[TripVersion]:
    """List immutable versions in business-version order."""
    return list(
        session.scalars(
            select(TripVersion)
            .where(TripVersion.trip_id == trip_id)
            .order_by(TripVersion.version)
        )
    )


def get_active_trip_version(session: Session, trip_id: str) -> TripVersion | None:
    """Resolve the active immutable version without mutating historical rows."""
    trip = get_trip(session, trip_id)
    if trip is None:
        return None
    if trip.active_version is None:
        return session.scalar(
            select(TripVersion)
            .where(
                TripVersion.trip_id == trip_id,
                TripVersion.version_role.in_(["primary", "replan", "rollback"]),
            )
            .order_by(TripVersion.version.desc())
        )
    return get_trip_version(session, trip_id, trip.active_version)


def next_trip_version(session: Session, trip_id: str) -> int:
    """Return the next collision-free immutable version number."""
    current = session.scalar(
        select(func.max(TripVersion.version)).where(TripVersion.trip_id == trip_id)
    )
    return int(current or 0) + 1


def get_review(session: Session, review_id: str, *, for_update: bool = False) -> TripReview | None:
    """Load one durable review record."""
    statement = select(TripReview).where(TripReview.id == review_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def get_current_review(session: Session, task: TripTask) -> TripReview | None:
    """Load the review referenced by the task's durable public snapshot."""
    if task.review_id is None:
        return None
    return get_review(session, task.review_id)


def list_trip_reviews(session: Session, trip_id: str) -> list[TripReview]:
    """List all review decisions and proposals without dropping superseded rounds."""
    return list(
        session.scalars(
            select(TripReview)
            .where(TripReview.trip_id == trip_id)
            .order_by(TripReview.created_at, TripReview.id)
        )
    )


def create_replan_review_request(
    session: Session,
    *,
    task_id: str,
    decision: TripReviewDecisionV2,
) -> tuple[TripTask, TripReview]:
    """Start a new replan workflow from the active immutable version."""
    if decision.action != "modify" or decision.changes is None:
        raise ValueError("A completed plan can only start a modify workflow.")
    task = _required_task(session, task_id, for_update=True)
    if task.status != "completed":
        raise ValueError("A new replan can only start from a completed task.")
    active = get_active_trip_version(session, task.trip_id)
    if active is None or active.native_payload is None:
        raise ValueError("The active version does not support structured replanning.")

    review_id = f"review_{uuid4().hex[:20]}"
    review = TripReview(
        id=review_id,
        trip_id=task.trip_id,
        task_id=task.id,
        workflow_type="replan",
        thread_id=f"{task.id}:replan:{review_id}",
        status="requested",
        base_version=active.version,
        proposed_version=next_trip_version(session, task.trip_id),
        decision_action="modify",
        reason=decision.reason or decision.changes.instruction,
        change_request=decision.changes.model_dump(mode="json"),
    )
    session.add(review)
    session.flush()
    task.status = "queued"
    task.stage = "replan_queued"
    task.progress = 80
    task.message = "Scoped replanning queued."
    task.review_id = review.id
    task.review_payload = review_public_payload(review)
    task.celery_task_id = None
    task.finished_at = None
    task.error_code = None
    task.error_message = None
    task.attempt_count = 0
    session.commit()
    session.refresh(task)
    session.refresh(review)
    return task, review


def record_pending_review(
    session: Session,
    *,
    task_id: str,
    workflow_type: str,
    thread_id: str,
    preview_payload: dict[str, Any],
    native_payload: dict[str, Any],
    validation_report: dict[str, Any],
    diff_payload: dict[str, Any],
    impact_scope: dict[str, Any] | None = None,
    refreshed_sources: Sequence[str] = (),
    base_version: int | None = None,
    proposed_version: int | None = None,
    reason: str = "",
) -> tuple[TripTask, TripReview]:
    """Persist an interrupted graph proposal and expose it through the task snapshot."""
    task = _required_task(session, task_id, for_update=True)
    current = get_review(session, task.review_id, for_update=True) if task.review_id else None
    if current is not None and current.status == "pending":
        review = current
    elif current is not None and current.status == "requested":
        review = current
    else:
        parent_review_id = current.id if current is not None else None
        if current is not None and current.status == "changes_requested":
            current.status = "superseded"
            current.resolved_at = datetime.now(timezone.utc)
        review = TripReview(
            id=f"review_{uuid4().hex[:20]}",
            trip_id=task.trip_id,
            task_id=task.id,
            workflow_type=workflow_type,
            thread_id=thread_id,
            status="pending",
            base_version=base_version,
            proposed_version=proposed_version,
            parent_review_id=parent_review_id,
            reason=reason or (current.reason if current is not None else ""),
            change_request=current.change_request if current is not None else None,
        )
        session.add(review)
        session.flush()

    review.status = "pending"
    review.decision_action = None
    review.preview_payload = preview_payload
    review.native_payload = native_payload
    review.validation_report = validation_report
    review.diff_payload = diff_payload
    review.impact_scope = impact_scope
    review.refreshed_sources = list(refreshed_sources)
    review.base_version = base_version
    review.proposed_version = proposed_version
    review.updated_at = datetime.now(timezone.utc)

    task.status = "awaiting_approval"
    task.stage = "awaiting_approval"
    task.progress = 90
    task.message = "Trip plan is awaiting human approval."
    task.result_payload = preview_payload
    task.review_id = review.id
    task.review_payload = review_public_payload(review)
    task.celery_task_id = None
    task.finished_at = None
    session.commit()
    session.refresh(task)
    session.refresh(review)
    task.review_payload = review_public_payload(review)
    session.commit()
    session.refresh(task)
    return task, review


def submit_review_decision(
    session: Session,
    *,
    task_id: str,
    decision: TripReviewDecisionV2,
) -> tuple[TripTask, TripReview]:
    """Persist a decision before dispatching graph resumption."""
    task = _required_task(session, task_id, for_update=True)
    if task.status != "awaiting_approval" or task.review_id is None:
        raise ValueError("Task is not awaiting approval.")
    review = get_review(session, task.review_id, for_update=True)
    if review is None or review.status != "pending":
        raise ValueError("The current review is no longer pending.")
    if (
        decision.action == "approve"
        and review.workflow_type == "replan"
        and not (review.diff_payload or {}).get("entries")
    ):
        raise ValueError("A replan proposal with no changes cannot be approved.")

    review.decision_action = decision.action
    review.reason = decision.reason or review.reason
    if decision.changes is not None:
        review.change_request = decision.changes.model_dump(mode="json")
    review.status = {
        "approve": "approved",
        "modify": "changes_requested",
        "reject": "rejected",
    }[decision.action]
    review.updated_at = datetime.now(timezone.utc)

    selected_review = review
    if review.workflow_type == "initial" and decision.action == "modify":
        changes = decision.changes
        if changes is None:
            raise ValueError("changes are required when action is modify")
        review.resolved_at = datetime.now(timezone.utc)
        selected_review = TripReview(
            id=f"review_{uuid4().hex[:20]}",
            trip_id=review.trip_id,
            task_id=review.task_id,
            workflow_type="replan",
            thread_id=f"{task.id}:replan:{review.id}",
            status="requested",
            base_version=None,
            proposed_version=1,
            parent_review_id=review.id,
            decision_action="modify",
            reason=decision.reason or changes.instruction,
            change_request=changes.model_dump(mode="json"),
            preview_payload=review.preview_payload,
            native_payload=review.native_payload,
        )
        session.add(selected_review)
        session.flush()

    task.status = "queued"
    task.stage = "review_resume"
    task.progress = 90
    task.message = f"Human review decision '{decision.action}' queued."
    task.review_id = selected_review.id
    task.review_payload = review_public_payload(selected_review)
    task.celery_task_id = None
    task.finished_at = None
    task.attempt_count = 0
    session.commit()
    session.refresh(task)
    session.refresh(selected_review)
    return task, selected_review


def mark_review_applied(session: Session, review_id: str) -> TripReview:
    """Mark an approved proposal as the source of an immutable version."""
    review = get_review(session, review_id, for_update=True)
    if review is None:
        raise LookupError(review_id)
    review.status = "applied"
    review.resolved_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(review)
    return review


def rollback_trip_version(
    session: Session,
    *,
    trip_id: str,
    target_version: int,
    reason: str,
) -> tuple[TripTask, TripReview, TripVersion]:
    """Create and activate a new immutable version copied from an older version."""
    from ..domain.trip_models import TripPlanV2
    from ..services.replanning import diff_plans

    trip = get_trip(session, trip_id)
    if trip is None:
        raise LookupError(trip_id)
    task = _task_for_trip(session, trip_id)
    if task.status != "completed":
        raise ValueError("Version rollback requires a completed task.")
    target = get_trip_version(session, trip_id, target_version)
    active = get_active_trip_version(session, trip_id)
    if target is None or active is None:
        raise LookupError(target_version)
    if target.version == active.version:
        raise ValueError("The requested version is already active.")
    if target.native_payload is None:
        raise ValueError("The target version has no structured payload.")

    new_version = next_trip_version(session, trip_id)
    review = TripReview(
        id=f"review_{uuid4().hex[:20]}",
        trip_id=trip_id,
        task_id=task.id,
        workflow_type="rollback",
        thread_id=f"{task.id}:rollback:{new_version}",
        status="applied",
        base_version=active.version,
        proposed_version=new_version,
        decision_action="approve",
        reason=reason,
        change_request=None,
        preview_payload=target.payload,
        native_payload=target.native_payload,
        validation_report=target.validation_report or {},
        refreshed_sources=[],
        resolved_at=datetime.now(timezone.utc),
    )
    if active.native_payload is not None:
        review.diff_payload = diff_plans(
            TripPlanV2.model_validate(active.native_payload),
            TripPlanV2.model_validate(target.native_payload),
            from_version=active.version,
            to_version=new_version,
        ).model_dump(mode="json")
    session.add(review)
    session.flush()

    record = save_trip_version(
        session,
        trip_id=trip_id,
        version=new_version,
        payload=target.payload,
        planner_engine=target.planner_engine,
        version_role="rollback",
        schema_version=target.schema_version,
        native_payload=target.native_payload,
        parent_version=active.version,
        review_id=review.id,
        change_reason=reason,
        change_sources=[f"version:{target_version}"],
        validation_report=target.validation_report or {},
        activate=True,
    )
    source_ids = list(
        session.scalars(
            select(TripSourceLink.source_id).where(
                TripSourceLink.trip_version_id == target.id
            )
        )
    )
    for source_id in source_ids:
        session.add(TripSourceLink(trip_version_id=record.id, source_id=source_id))

    task.status = "completed"
    task.stage = "completed"
    task.progress = 100
    task.message = f"Trip version {target_version} restored as version {new_version}."
    task.result_payload = target.payload
    task.review_id = review.id
    task.review_payload = review_public_payload(review)
    task.finished_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(task)
    session.refresh(review)
    session.refresh(record)
    return task, review, record


def review_public_payload(review: TripReview) -> dict[str, Any]:
    """Serialize only review data intended for API consumers."""
    return {
        "review_id": review.id,
        "trip_id": review.trip_id,
        "task_id": review.task_id,
        "workflow_type": review.workflow_type,
        "status": review.status,
        "base_version": review.base_version,
        "proposed_version": review.proposed_version,
        "parent_review_id": review.parent_review_id,
        "reason": review.reason,
        "change_request": review.change_request,
        "impact_scope": review.impact_scope,
        "refreshed_sources": review.refreshed_sources or [],
        "validation_report": review.validation_report or {"issues": []},
        "diff": review.diff_payload or {},
        "preview": review.preview_payload,
        "created_at": review.created_at.isoformat(),
        "updated_at": review.updated_at.isoformat(),
        "resolved_at": review.resolved_at.isoformat() if review.resolved_at else None,
    }


def stale_recoverable_tasks(session: Session, stale_after_seconds: int) -> list[TripTask]:
    """Return work whose broker dispatch or execution heartbeat may have been lost."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
    return list(
        session.scalars(
            select(TripTask).where(
                (TripTask.status == "cancel_requested")
                | (
                    TripTask.status.in_(["queued", "retrying"])
                    & (
                        TripTask.celery_task_id.is_(None)
                        | (TripTask.updated_at < cutoff)
                    )
                )
                | ((TripTask.status == "processing") & (TripTask.updated_at < cutoff))
            )
        )
    )


def task_needs_recovery(
    task: TripTask,
    stale_after_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    """Revalidate a recovery candidate after acquiring its row lock."""
    if task.status in FINAL_TASK_STATUSES:
        return False
    if task.status == "cancel_requested" or task.cancel_requested:
        return True

    current_time = now or datetime.now(timezone.utc)
    updated_at = task.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    stale = updated_at < current_time - timedelta(seconds=stale_after_seconds)
    if task.status in {"queued", "retrying"}:
        return task.celery_task_id is None or stale
    return task.status == "processing" and stale


def _task_for_trip(session: Session, trip_id: str) -> TripTask:
    task = get_task_for_trip(session, trip_id)
    if task is None:
        raise RuntimeError(f"Trip {trip_id} has no durable task.")
    return task


def _ensure_same_idempotent_request(trip: Trip, request_payload: dict[str, Any]) -> None:
    if trip.request_payload != request_payload:
        raise IdempotencyConflictError(
            "Idempotency-Key has already been used with a different request payload."
        )


def _required_task(session: Session, task_id: str, *, for_update: bool = False) -> TripTask:
    task = get_task(session, task_id, for_update=for_update)
    if task is None:
        raise LookupError(task_id)
    return task
