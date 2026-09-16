"""Durable v2 trip submission, status, cancellation, retry, and event endpoints."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.orm import Session

from ...db.models import TripTask
from ...db.repository import (
    IdempotencyConflictError,
    attach_celery_task,
    create_or_get_task,
    create_replan_review_request,
    create_trip_feedback,
    get_active_trip_version,
    get_task,
    get_task_for_trip,
    get_trip,
    get_trip_version,
    list_task_telemetry,
    list_trip_reviews,
    list_trip_versions,
    prepare_retry,
    request_cancellation,
    review_public_payload,
    rollback_trip_version,
    submit_review_decision,
    update_task_state,
)
from ...db.session import SessionLocal, get_db_session
from ...domain.error_models import (
    V2_CONFLICT_ERROR_EXAMPLE,
    V2_INTERNAL_ERROR_EXAMPLE,
    V2_NOT_FOUND_ERROR_EXAMPLE,
    V2_VALIDATION_ERROR_EXAMPLE,
    ErrorEnvelopeV2,
)
from ...domain.feedback_models import TripFeedbackRecordV2, TripFeedbackRequestV2
from ...domain.observability_models import TelemetryEventV2
from ...domain.review_models import (
    PlanDiffV2,
    ReplanRequestV2,
    TripReviewDecisionV2,
    TripReviewRecordV2,
    TripVersionRecordV2,
    VersionRollbackRequestV2,
)
from ...domain.task_models import TRIP_TASK_RECORD_V2_EXAMPLE, TripTaskRecordV2
from ...domain.trip_models import TRIP_REQUEST_V2_EXAMPLE, TripPlanV2, TripRequestV2
from ...domain.trip_resource_models import TripResourceV2
from ...services.guardrails import enforce_spend_guardrails
from ...services.observability import sanitize_metadata
from ...services.replanning import diff_plans
from ...services.task_events import (
    TASK_STREAM_STOP_STATUSES,
    publish_task_event,
    redis_url,
    task_channel,
    task_snapshot,
)
from ...workers.trip_tasks import enqueue_trip_task

router = APIRouter(prefix="/trips", tags=["API v2"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TripTaskRecordV2,
    summary="Submit a durable v2 trip request",
    description=(
        "Persist the canonical request and task in PostgreSQL before dispatching the configured "
        "planner through Celery. Repeated requests are deduplicated by Idempotency-Key or payload."
    ),
    responses={
        202: {
            "description": "Durable task accepted.",
            "content": {"application/json": {"example": TRIP_TASK_RECORD_V2_EXAMPLE}},
        },
        404: {
            "model": ErrorEnvelopeV2,
            "content": {"application/json": {"example": V2_NOT_FOUND_ERROR_EXAMPLE}},
        },
        409: {
            "model": ErrorEnvelopeV2,
            "content": {"application/json": {"example": V2_CONFLICT_ERROR_EXAMPLE}},
        },
        422: {
            "model": ErrorEnvelopeV2,
            "content": {"application/json": {"example": V2_VALIDATION_ERROR_EXAMPLE}},
        },
        500: {
            "model": ErrorEnvelopeV2,
            "content": {"application/json": {"example": V2_INTERNAL_ERROR_EXAMPLE}},
        },
    },
)
def create_trip(
    session: DbSession,
    http_request: Request,
    request: TripRequestV2 = Body(
        ...,
        openapi_examples={
            "durable_submission": {
                "summary": "Valid durable trip submission",
                "value": TRIP_REQUEST_V2_EXAMPLE,
            }
        },
    ),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> TripTaskRecordV2:
    """Persist before dispatch so an API restart cannot lose accepted work."""
    payload = request.model_dump(mode="json")
    enforce_spend_guardrails(http_request, session, payload)
    try:
        task, created = create_or_get_task(
            session,
            request_payload=payload,
            idempotency_key=_digest_idempotency_key(payload, idempotency_key),
            trace_id=http_request.state.trace_id,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if created:
        task = _dispatch_or_fail(session, task)
    publish_task_event(task)
    return _response(task)


@router.get(
    "/tasks/{task_id}",
    response_model=TripTaskRecordV2,
    summary="Read durable task status",
)
def read_task(task_id: str, session: DbSession) -> TripTaskRecordV2:
    """Read current state from PostgreSQL, never from process memory."""
    return _response(_required_task(session, task_id))


@router.get(
    "/tasks/{task_id}/telemetry",
    response_model=list[TelemetryEventV2],
    summary="Read sanitized task telemetry",
)
def read_task_telemetry(task_id: str, session: DbSession) -> list[TelemetryEventV2]:
    """Expose operational metrics only; prompts, credentials, and outputs are never stored."""
    _required_task(session, task_id)
    return [
        TelemetryEventV2(
            trace_id=event.trace_id,
            task_id=event.task_id,
            trip_id=event.trip_id,
            component=event.component,
            operation=event.operation,
            status=event.status,
            node=event.node,
            tool=event.tool,
            latency_ms=event.latency_ms,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            total_tokens=event.total_tokens,
            model_cost_usd=event.model_cost_usd,
            retry_count=event.retry_count,
            cache_hit=event.cache_hit,
            model_id=event.model_id,
            prompt_version=event.prompt_version,
            workflow_version=event.workflow_version,
            tool_version=event.tool_version,
            metadata=sanitize_metadata(event.event_metadata),
            created_at=event.created_at,
        )
        for event in list_task_telemetry(session, task_id)
    ]


@router.get(
    "/{trip_id}",
    response_model=TripResourceV2,
    summary="Read a canonical trip resource",
)
def read_trip(trip_id: str, session: DbSession) -> TripResourceV2:
    trip = get_trip(session, trip_id)
    task = get_task_for_trip(session, trip_id)
    if trip is None or task is None:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return TripResourceV2(
        trip_id=trip.id,
        request=trip.request_payload,
        task=_response(task),
        active_version=trip.active_version,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
    )


@router.post(
    "/{trip_id}/approve",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TripTaskRecordV2,
    summary="Approve the current durable proposal",
)
def approve_trip(trip_id: str, session: DbSession, http_request: Request) -> TripTaskRecordV2:
    task = _required_trip_task(session, trip_id)
    return review_task(
        task.id,
        TripReviewDecisionV2(action="approve"),
        session,
        http_request,
    )


@router.post(
    "/{trip_id}/replan",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TripTaskRecordV2,
    summary="Start a scoped replan for a trip",
)
def replan_trip(
    trip_id: str,
    changes: ReplanRequestV2,
    session: DbSession,
    http_request: Request,
) -> TripTaskRecordV2:
    task = _required_trip_task(session, trip_id)
    return review_task(
        task.id,
        TripReviewDecisionV2(action="modify", reason=changes.instruction, changes=changes),
        session,
        http_request,
    )


@router.post(
    "/{trip_id}/feedback",
    status_code=status.HTTP_201_CREATED,
    response_model=TripFeedbackRecordV2,
    summary="Persist bounded feedback for a trip",
)
def submit_trip_feedback(
    trip_id: str,
    feedback: TripFeedbackRequestV2,
    session: DbSession,
) -> TripFeedbackRecordV2:
    task = _required_trip_task(session, trip_id)
    if feedback.version is not None and get_trip_version(session, trip_id, feedback.version) is None:
        raise HTTPException(status_code=404, detail="Trip version not found.")
    record = create_trip_feedback(
        session,
        trip_id=trip_id,
        task_id=task.id,
        feedback=feedback,
    )
    return TripFeedbackRecordV2(
        feedback_id=record.id,
        trip_id=record.trip_id,
        task_id=record.task_id,
        rating=record.rating,
        category=feedback.category,
        comment=record.comment,
        version=record.version,
        created_at=record.created_at,
    )


@router.post(
    "/tasks/{task_id}/cancel",
    response_model=TripTaskRecordV2,
    summary="Cancel a queued or running task",
)
def cancel_task(task_id: str, session: DbSession) -> TripTaskRecordV2:
    """Cancel queued work immediately or request cooperative running cancellation."""
    _required_task(session, task_id)
    task = request_cancellation(session, task_id)
    publish_task_event(task)
    return _response(task)


@router.post(
    "/tasks/{task_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TripTaskRecordV2,
    summary="Retry a failed or cancelled task",
)
def retry_task(task_id: str, session: DbSession, http_request: Request) -> TripTaskRecordV2:
    """Reset the persisted attempt policy and dispatch a new Celery message."""
    _required_task(session, task_id)
    enforce_spend_guardrails(http_request, session, {"task_id": task_id, "operation": "retry"})
    try:
        task = prepare_retry(session, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    task = _dispatch_or_fail(session, task)
    publish_task_event(task)
    return _response(task)


@router.post(
    "/tasks/{task_id}/review",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TripTaskRecordV2,
    summary="Approve, modify, or reject a durable trip proposal",
)
def review_task(
    task_id: str,
    decision: TripReviewDecisionV2,
    session: DbSession,
    http_request: Request,
) -> TripTaskRecordV2:
    """Persist the human decision before dispatching graph continuation."""
    task = _required_task(session, task_id)
    enforce_spend_guardrails(
        http_request,
        session,
        {"task_id": task_id, "operation": "review", "decision": decision.model_dump(mode="json")},
    )
    try:
        if task.status == "completed":
            task, _review = create_replan_review_request(
                session,
                task_id=task_id,
                decision=decision,
            )
        else:
            task, _review = submit_review_decision(
                session,
                task_id=task_id,
                decision=decision,
            )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    task = _dispatch_or_fail(session, task)
    publish_task_event(task)
    return _response(task)


@router.get(
    "/{trip_id}/reviews",
    response_model=list[TripReviewRecordV2],
    summary="List durable review rounds for a trip",
)
def read_trip_reviews(trip_id: str, session: DbSession) -> list[TripReviewRecordV2]:
    if get_trip(session, trip_id) is None:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return [
        TripReviewRecordV2.model_validate(review_public_payload(review))
        for review in list_trip_reviews(session, trip_id)
    ]


@router.get(
    "/{trip_id}/versions",
    response_model=list[TripVersionRecordV2],
    summary="List immutable versions for a trip",
)
def read_trip_versions(trip_id: str, session: DbSession) -> list[TripVersionRecordV2]:
    trip = get_trip(session, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found.")
    active = get_active_trip_version(session, trip_id)
    return [
        _version_response(version, active_version=(active.version if active else None))
        for version in list_trip_versions(session, trip_id)
    ]


@router.get(
    "/{trip_id}/versions/{version}",
    response_model=TripVersionRecordV2,
    summary="Read one immutable trip version",
)
def read_trip_version(
    trip_id: str,
    version: int,
    session: DbSession,
) -> TripVersionRecordV2:
    record = get_trip_version(session, trip_id, version)
    if record is None:
        raise HTTPException(status_code=404, detail="Trip version not found.")
    active = get_active_trip_version(session, trip_id)
    return _version_response(record, active_version=(active.version if active else None), detail=True)


@router.get(
    "/{trip_id}/versions/{from_version}/compare/{to_version}",
    response_model=PlanDiffV2,
    summary="Compare two immutable structured trip versions",
)
def compare_trip_versions(
    trip_id: str,
    from_version: int,
    to_version: int,
    session: DbSession,
) -> PlanDiffV2:
    before = get_trip_version(session, trip_id, from_version)
    after = get_trip_version(session, trip_id, to_version)
    if before is None or after is None:
        raise HTTPException(status_code=404, detail="Trip version not found.")
    if before.native_payload is None or after.native_payload is None:
        raise HTTPException(status_code=409, detail="Both versions require structured payloads.")
    return diff_plans(
        TripPlanV2.model_validate(before.native_payload),
        TripPlanV2.model_validate(after.native_payload),
        from_version=from_version,
        to_version=to_version,
    )


@router.post(
    "/{trip_id}/versions/{version}/rollback",
    response_model=TripVersionRecordV2,
    summary="Restore an older version as a new immutable version",
)
def rollback_version(
    trip_id: str,
    version: int,
    request: VersionRollbackRequestV2,
    session: DbSession,
) -> TripVersionRecordV2:
    try:
        task, _review, record = rollback_trip_version(
            session,
            trip_id=trip_id,
            target_version=version,
            reason=request.reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Trip version not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    publish_task_event(task)
    return _version_response(record, active_version=record.version, detail=True)


@router.websocket("/tasks/{task_id}/ws")
async def task_events(websocket: WebSocket, task_id: str) -> None:
    """Stream Redis Pub/Sub events while periodically reconciling from PostgreSQL."""
    await websocket.accept()
    redis_client = AsyncRedis.from_url(redis_url(), decode_responses=True)
    pubsub = redis_client.pubsub()
    try:
        # Subscribe before reading the snapshot so no transition can fall into a read/subscribe gap.
        await pubsub.subscribe(task_channel(task_id))
        with SessionLocal() as session:
            task = get_task(session, task_id)
            if task is None:
                await websocket.send_json({"error": {"code": "not_found", "message": "Task not found."}})
                await websocket.close(code=4404)
                return
            initial = task_snapshot(task)
        await websocket.send_json(initial)
        if initial["status"] in TASK_STREAM_STOP_STATUSES:
            await websocket.close()
            return

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is not None:
                event = json.loads(message["data"])
                await websocket.send_json(event)
                if event["status"] in TASK_STREAM_STOP_STATUSES:
                    break
            else:
                with SessionLocal() as session:
                    current = get_task(session, task_id)
                    if current is None:
                        break
                    snapshot = task_snapshot(current)
                if snapshot["status"] in TASK_STREAM_STOP_STATUSES:
                    await websocket.send_json(snapshot)
                    break
    except WebSocketDisconnect:
        return
    finally:
        await pubsub.aclose()
        await redis_client.aclose()


def _dispatch_or_fail(session: Session, task: TripTask) -> TripTask:
    try:
        broker_task_id = enqueue_trip_task(task.id)
    except Exception as exc:
        failed = update_task_state(
            session,
            task.id,
            status="failed",
            stage="dispatch_failed",
            message="Task could not be dispatched.",
            error_code="dispatch_failed",
            error_message=type(exc).__name__,
            finished=True,
        )
        publish_task_event(failed)
        raise HTTPException(status_code=503, detail="Task broker is unavailable.") from exc

    try:
        return attach_celery_task(session, task.id, broker_task_id)
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=503,
            detail="Task dispatch was sent but could not be confirmed; recovery is pending.",
        ) from exc


def _required_task(session: Session, task_id: str) -> TripTask:
    task = get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


def _required_trip_task(session: Session, trip_id: str) -> TripTask:
    task = get_task_for_trip(session, trip_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return task


def _response(task: TripTask) -> TripTaskRecordV2:
    return TripTaskRecordV2.model_validate(task_snapshot(task))


def _version_response(
    version: Any,
    *,
    active_version: int | None,
    detail: bool = False,
) -> TripVersionRecordV2:
    return TripVersionRecordV2(
        trip_id=version.trip_id,
        version=version.version,
        active=version.version == active_version,
        parent_version=version.parent_version,
        planner_engine=version.planner_engine,
        version_role=version.version_role,
        schema_version=version.schema_version,
        review_id=version.review_id,
        change_reason=version.change_reason or "",
        change_sources=version.change_sources or [],
        validation_report=version.validation_report or {"issues": []},
        model_id=version.model_id,
        prompt_version=version.prompt_version,
        workflow_version=version.workflow_version,
        tool_versions=version.tool_versions or {},
        usage_summary=version.usage_summary or {},
        created_at=version.created_at,
        payload=version.payload if detail else None,
        native_payload=version.native_payload if detail else None,
    )


def _digest_idempotency_key(payload: dict[str, Any], supplied_key: str | None) -> str:
    if supplied_key is not None and len(supplied_key) > 256:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long.")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    namespace = f"header:{supplied_key}" if supplied_key else f"payload:{canonical}"
    return hashlib.sha256(namespace.encode("utf-8")).hexdigest()
