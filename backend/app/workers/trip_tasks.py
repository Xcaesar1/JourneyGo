"""Durable Celery execution for feature-flagged JourneyOps planners."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter, sleep
from typing import Any, Literal
from uuid import uuid4

from celery import signals
from celery.exceptions import Retry
from redis import Redis

from ..config import get_settings
from ..db.repository import (
    FINAL_TASK_STATUSES,
    attach_celery_task,
    get_active_trip_version,
    get_current_review,
    get_task,
    get_trip,
    get_trip_version,
    mark_review_applied,
    next_trip_version,
    record_pending_review,
    record_telemetry_event,
    review_public_payload,
    save_trip_version,
    stale_recoverable_tasks,
    task_needs_recovery,
    update_task_state,
)
from ..db.session import SessionLocal
from ..domain.research_models import SourceEvidence
from ..domain.review_models import ReplanRequestV2
from ..domain.trip_models import TripPlanV2, TripRequestV2
from ..models.schemas import CityStay, TripPlanResponse, TripRequest
from ..services.observability import (
    PROMPT_VERSION,
    TOOL_VERSIONS,
    WORKFLOW_VERSION,
    sanitize_metadata,
)
from ..services.task_events import publish_task_event, redis_url, task_snapshot
from .celery_app import celery_app

LOGGER = logging.getLogger(__name__)
TASK_NAME = "journeyops.plan_trip"
_RECOVERY_STOP = threading.Event()
_RECOVERY_THREAD: threading.Thread | None = None
_RECOVERY_THREAD_GUARD = threading.Lock()
_REDACTED = "[REDACTED]"
_AUTH_VALUE_PATTERN = re.compile(r"(?i)\b(Bearer|Basic)\s+[^\s,;]+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(?<![\w-])([\"']?(?:api[_-]?key|authorization|auth[_-]?token|"
    r"access[_-]?token|secret|password|passwd|cookie)[\"']?)(\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_URL_CREDENTIAL_PATTERN = re.compile(r"(?i)(https?://)[^\s/@:]+:[^\s/@]+@")
_PROVIDER_TOKEN_PATTERN = re.compile(r"(?i)\bsk-[a-z0-9_-]{8,}\b")


class TaskCancelled(Exception):
    """Raised when a persisted cooperative cancellation is observed."""


PlannerEngine = Literal["legacy", "journey_graph"]


@dataclass(frozen=True)
class PlannerExecution:
    """One planner output plus its persistence metadata."""

    engine: PlannerEngine
    client_payload: dict[str, Any]
    schema_version: str
    native_payload: dict[str, Any] | None = None
    source_evidence: tuple[SourceEvidence, ...] = ()
    workflow_status: Literal["completed", "awaiting_approval", "rejected"] = "completed"
    review_workflow_type: Literal["initial", "replan"] | None = None
    review_thread_id: str | None = None
    review_base_version: int | None = None
    review_proposed_version: int | None = None
    review_reason: str = ""
    impact_scope: dict[str, Any] | None = None
    diff_payload: dict[str, Any] | None = None
    validation_report: dict[str, Any] | None = None
    refreshed_sources: tuple[str, ...] = ()
    model_id: str = "unknown"
    prompt_version: str = "legacy"
    workflow_version: str = "legacy"
    tool_versions: dict[str, str] | None = None
    metrics: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlannerRunSet:
    """Primary output and optional shadow-comparison output."""

    primary: PlannerExecution
    comparison: PlannerExecution | None = None


@dataclass(frozen=True)
class ReviewContext:
    """Detached persisted review state passed into one Worker execution."""

    review_id: str
    workflow_type: Literal["initial", "replan"]
    thread_id: str
    status: str
    base_version: int | None
    proposed_version: int | None
    action: str | None
    reason: str
    change_request: dict[str, Any] | None
    preview_payload: dict[str, Any] | None
    native_payload: dict[str, Any] | None


def _review_context(review: Any | None) -> ReviewContext | None:
    if review is None:
        return None
    return ReviewContext(
        review_id=review.id,
        workflow_type=review.workflow_type,
        thread_id=review.thread_id,
        status=review.status,
        base_version=review.base_version,
        proposed_version=review.proposed_version,
        action=review.decision_action,
        reason=review.reason,
        change_request=review.change_request,
        preview_payload=review.preview_payload,
        native_payload=review.native_payload,
    )


def enqueue_trip_task(task_id: str) -> str:
    """Dispatch one durable task and return the broker task identifier."""
    result = celery_app.send_task(TASK_NAME, args=[task_id])
    return result.id


def recover_incomplete_tasks(stale_after_seconds: int | None = None) -> dict[str, int]:
    """Recover undispatched and stale work when a worker becomes ready."""
    stale_after = (
        stale_after_seconds
        if stale_after_seconds is not None
        else int(os.getenv("TRIP_TASK_STALE_AFTER", "120"))
    )
    summary = {"dispatched": 0, "failed": 0, "cancelled": 0}
    with SessionLocal() as session:
        candidates = stale_recoverable_tasks(session, stale_after)

    for candidate in candidates:
        with SessionLocal() as session:
            task = get_task(session, candidate.id, for_update=True)
            if task is None or not task_needs_recovery(task, stale_after):
                continue
            if task.status == "cancel_requested" or task.cancel_requested:
                task = update_task_state(
                    session,
                    task.id,
                    status="cancelled",
                    stage="cancelled",
                    message="Task cancellation recovered after worker interruption.",
                    finished=True,
                )
                publish_task_event(task)
                summary["cancelled"] += 1
                continue
            if task.status == "processing" and _execution_lock_active(task.id):
                continue
            if task.status == "processing" and task.attempt_count >= task.max_attempts:
                task.status = "failed"
                task.stage = "failed"
                task.message = "Worker recovery policy exhausted."
                task.error_code = "worker_lost"
                task.error_message = "Task exceeded its maximum recovery attempts."
                session.commit()
                session.refresh(task)
                publish_task_event(task)
                summary["failed"] += 1
                continue
            task.status = "retrying" if task.status == "processing" else "queued"
            task.stage = "worker_recovery" if task.status == "retrying" else "queued"
            task.message = "Task recovered after worker interruption."
            recovery_claim = f"recovery-{uuid4().hex}"
            task.celery_task_id = recovery_claim
            session.commit()
            session.refresh(task)
            task_id = task.id

        broker_task_id = enqueue_trip_task(task_id)
        with SessionLocal() as session:
            task = attach_celery_task(
                session,
                task_id,
                broker_task_id,
                expected_celery_task_id=recovery_claim,
            )
            publish_task_event(task)
        summary["dispatched"] += 1

    return summary


@signals.worker_ready.connect
def _recover_when_worker_is_ready(**_: Any) -> None:
    _run_recovery_safely("startup")
    _start_recovery_thread()


@signals.worker_shutdown.connect
def _stop_recovery_when_worker_shuts_down(**_: Any) -> None:
    _RECOVERY_STOP.set()
    thread = _RECOVERY_THREAD
    if thread is not None:
        thread.join(timeout=2)


def _run_recovery_safely(trigger: str) -> None:
    try:
        summary = recover_incomplete_tasks()
        LOGGER.info("Worker recovery complete (%s): %s", trigger, summary)
    except Exception as exc:
        LOGGER.error("Worker recovery failed (%s): %s", trigger, type(exc).__name__, exc_info=True)


def _start_recovery_thread() -> None:
    global _RECOVERY_THREAD
    with _RECOVERY_THREAD_GUARD:
        if _RECOVERY_THREAD is not None and _RECOVERY_THREAD.is_alive():
            return
        _RECOVERY_STOP.clear()
        _RECOVERY_THREAD = threading.Thread(
            target=_recovery_loop,
            name="journeyops-task-recovery",
            daemon=True,
        )
        _RECOVERY_THREAD.start()


def _recovery_loop() -> None:
    interval = max(5, int(os.getenv("TRIP_TASK_RECOVERY_INTERVAL", "60")))
    while not _RECOVERY_STOP.wait(interval):
        _run_recovery_safely("periodic")


@celery_app.task(bind=True, name=TASK_NAME)
def run_trip_planning(self: Any, task_id: str) -> dict[str, Any]:
    """Execute one persisted task with late acknowledgement and idempotent completion."""
    redis_client = Redis.from_url(redis_url(), decode_responses=True)
    lock_timeout = int(os.getenv("TRIP_TASK_LOCK_TIMEOUT", "90"))
    lock = redis_client.lock(
        f"journeyops:task-lock:{task_id}",
        timeout=lock_timeout,
        blocking_timeout=1,
        thread_local=False,
    )
    acquired = lock.acquire(blocking=True)
    if not acquired:
        redis_client.close()
        raise self.retry(countdown=5, max_retries=24)

    renewal_stop = threading.Event()
    renewal_thread = threading.Thread(
        target=_renew_lock,
        args=(lock, lock_timeout, renewal_stop, task_id),
        daemon=True,
    )
    renewal_thread.start()
    try:
        return _execute_task(self, task_id, lock, lock_timeout)
    finally:
        renewal_stop.set()
        renewal_thread.join(timeout=2)
        try:
            lock.release()
        except Exception:
            pass
        redis_client.close()


def _execute_task(self: Any, task_id: str, lock: Any, lock_timeout: int) -> dict[str, Any]:
    with SessionLocal() as session:
        task = get_task(session, task_id, for_update=True)
        if task is None:
            return {"task_id": task_id, "status": "missing"}
        if task.status in FINAL_TASK_STATUSES:
            return task_snapshot(task)
        if task.cancel_requested:
            task = update_task_state(
                session,
                task_id,
                status="cancelled",
                stage="cancelled",
                message="Task cancelled.",
                finished=True,
            )
            publish_task_event(task)
            return task_snapshot(task)
        current_review = get_current_review(session, task)
        review_context = _review_context(current_review)
        actionable_review = current_review is not None and current_review.status in {
            "requested",
            "approved",
            "changes_requested",
            "rejected",
        }
        existing_version = get_active_trip_version(session, task.trip_id)
        if existing_version is not None and not actionable_review:
            task = update_task_state(
                session,
                task_id,
                status="completed",
                stage="completed",
                progress=100,
                message="Active trip version recovered after redelivery.",
                result_payload=existing_version.payload,
                finished=True,
            )
            publish_task_event(task)
            return task_snapshot(task)
        if task.attempt_count >= task.max_attempts:
            task = update_task_state(
                session,
                task_id,
                status="failed",
                stage="failed",
                message="Task attempt policy exhausted.",
                error_code="attempts_exhausted",
                error_message="Task reached its maximum execution attempts.",
                finished=True,
            )
            publish_task_event(task)
            return task_snapshot(task)

        trip = get_trip(session, task.trip_id)
        if trip is None:
            raise RuntimeError(f"Task {task_id} references a missing trip.")
        request_payload = trip.request_payload
        task = update_task_state(
            session,
            task_id,
            status="processing",
            stage="initializing",
            progress=5,
            message="Planner worker started.",
            increment_attempt=True,
        )
        publish_task_event(task)
        attempt_count = task.attempt_count
        max_attempts = task.max_attempts
        trip_id = task.trip_id
        trace_id = task.trace_id
        record_telemetry_event(
            session,
            trace_id=trace_id,
            task_id=task_id,
            trip_id=trip_id,
            component="worker",
            operation="task_attempt",
            status="started",
            retry_count=max(0, attempt_count - 1),
            workflow_version=WORKFLOW_VERSION,
        )

    async def progress_callback(stage: str, message: str, progress: int) -> None:
        with SessionLocal() as progress_session:
            current = get_task(progress_session, task_id)
            if current is None or current.cancel_requested:
                raise TaskCancelled(task_id)
            updated = update_task_state(
                progress_session,
                task_id,
                status="processing",
                stage=stage,
                progress=progress,
                message=message,
            )
            publish_task_event(updated)
        try:
            lock.extend(lock_timeout, replace_ttl=True)
        except Exception:
            LOGGER.warning("Unable to extend task lock for %s", task_id)

    try:
        if review_context is not None and review_context.workflow_type == "replan":
            planner_runs = PlannerRunSet(
                primary=asyncio.run(
                    _run_replan_planner(
                        task_id,
                        trip_id,
                        request_payload,
                        progress_callback,
                        review_context,
                    )
                )
            )
        else:
            planner_runs = asyncio.run(
                _run_configured_planners(
                    task_id,
                    trip_id,
                    request_payload,
                    progress_callback,
                    review_context=review_context,
                )
            )
        result_payload = planner_runs.primary.client_payload
        primary = planner_runs.primary
        with SessionLocal() as telemetry_session:
            _persist_execution_telemetry(
                telemetry_session,
                trace_id=trace_id,
                task_id=task_id,
                trip_id=trip_id,
                execution=primary,
            )
        if primary.workflow_status == "awaiting_approval":
            if primary.native_payload is None or primary.review_thread_id is None:
                raise RuntimeError(
                    "Interrupted planner did not provide a reviewable native proposal."
                )
            with SessionLocal() as session:
                waiting, _review = record_pending_review(
                    session,
                    task_id=task_id,
                    workflow_type=primary.review_workflow_type or "initial",
                    thread_id=primary.review_thread_id,
                    preview_payload=result_payload,
                    native_payload=primary.native_payload,
                    validation_report=primary.validation_report or {"issues": []},
                    diff_payload=primary.diff_payload or {},
                    impact_scope=primary.impact_scope,
                    refreshed_sources=primary.refreshed_sources,
                    base_version=primary.review_base_version,
                    proposed_version=primary.review_proposed_version,
                    reason=primary.review_reason,
                )
                publish_task_event(waiting)
                return task_snapshot(waiting)

        if primary.workflow_status == "rejected":
            with SessionLocal() as session:
                current = get_task(session, task_id, for_update=True)
                if current is None:
                    raise LookupError(task_id)
                review = get_current_review(session, current)
                if review is not None:
                    review.status = "rejected"
                    review.resolved_at = datetime.now(timezone.utc)
                    current.review_payload = review_public_payload(review)
                active = get_active_trip_version(session, trip_id)
                keep_active_version = (
                    review is not None and review.workflow_type == "replan" and active is not None
                )
                rejected = update_task_state(
                    session,
                    task_id,
                    status=("completed" if keep_active_version else "rejected"),
                    stage=("completed" if keep_active_version else "rejected"),
                    progress=100,
                    message=(
                        "Replan proposal rejected; the active trip version was preserved."
                        if keep_active_version
                        else "Trip plan was rejected by the reviewer."
                    ),
                    result_payload=(active.payload if active is not None else result_payload),
                    finished=True,
                )
                publish_task_event(rejected)
                return task_snapshot(rejected)

        with SessionLocal() as session:
            current = get_task(session, task_id)
            if current is None or current.cancel_requested:
                raise TaskCancelled(task_id)
            persisted_review = get_current_review(session, current)
            primary_version = (
                persisted_review.proposed_version
                if persisted_review is not None and persisted_review.proposed_version is not None
                else 1
            )
            save_trip_version(
                session,
                trip_id=trip_id,
                version=primary_version,
                payload=result_payload,
                planner_engine=primary.engine,
                version_role=("replan" if primary.review_workflow_type == "replan" else "primary"),
                schema_version=primary.schema_version,
                native_payload=primary.native_payload,
                source_evidence=primary.source_evidence,
                parent_version=(persisted_review.base_version if persisted_review else None),
                review_id=(persisted_review.id if persisted_review else None),
                change_reason=(persisted_review.reason if persisted_review else "Initial plan"),
                change_sources=primary.refreshed_sources,
                validation_report=primary.validation_report or {},
                model_id=primary.model_id,
                prompt_version=primary.prompt_version,
                workflow_version=primary.workflow_version,
                tool_versions=primary.tool_versions or {},
                usage_summary=_usage_summary(primary.metrics),
                activate=True,
            )
            if planner_runs.comparison is not None:
                comparison = planner_runs.comparison
                save_trip_version(
                    session,
                    trip_id=trip_id,
                    version=next_trip_version(session, trip_id),
                    payload=comparison.client_payload,
                    planner_engine=comparison.engine,
                    version_role="comparison",
                    schema_version=comparison.schema_version,
                    native_payload=comparison.native_payload,
                    source_evidence=comparison.source_evidence,
                    model_id=comparison.model_id,
                    prompt_version=comparison.prompt_version,
                    workflow_version=comparison.workflow_version,
                    tool_versions=comparison.tool_versions or {},
                    usage_summary=_usage_summary(comparison.metrics),
                )
            if persisted_review is not None:
                applied = mark_review_applied(session, persisted_review.id)
                current = get_task(session, task_id, for_update=True)
                if current is not None:
                    current.review_payload = review_public_payload(applied)
                    session.commit()
            completed = update_task_state(
                session,
                task_id,
                status="completed",
                stage="completed",
                progress=100,
                message="Trip plan generated successfully.",
                result_payload=result_payload,
                finished=True,
            )
            record_telemetry_event(
                session,
                trace_id=trace_id,
                task_id=task_id,
                trip_id=trip_id,
                component="worker",
                operation="task_attempt",
                status="completed",
                retry_count=max(0, attempt_count - 1),
                model_id=primary.model_id,
                prompt_version=primary.prompt_version,
                workflow_version=primary.workflow_version,
            )
            publish_task_event(completed)
            return task_snapshot(completed)
    except TaskCancelled:
        with SessionLocal() as session:
            cancelled = update_task_state(
                session,
                task_id,
                status="cancelled",
                stage="cancelled",
                message="Task cancelled.",
                finished=True,
            )
            publish_task_event(cancelled)
            return task_snapshot(cancelled)
    except Retry:
        raise
    except Exception as exc:
        retryable = not isinstance(exc, (ValueError, TypeError))
        if retryable and attempt_count < max_attempts:
            with SessionLocal() as session:
                retrying = update_task_state(
                    session,
                    task_id,
                    status="retrying",
                    stage="retrying",
                    message=f"Planner attempt {attempt_count} failed; retry scheduled.",
                    error_code="planner_retry",
                    error_message=_safe_error_message(exc),
                )
                record_telemetry_event(
                    session,
                    trace_id=trace_id,
                    task_id=task_id,
                    trip_id=trip_id,
                    component="worker",
                    operation="task_attempt",
                    status="retrying",
                    retry_count=max(0, attempt_count - 1),
                    metadata={"error_type": type(exc).__name__},
                )
                publish_task_event(retrying)
            raise self.retry(
                exc=exc,
                countdown=min(30, 2**attempt_count),
                max_retries=max_attempts - 1,
            )

        with SessionLocal() as session:
            failed = update_task_state(
                session,
                task_id,
                status="failed",
                stage="failed",
                message="Trip planner failed.",
                error_code="planner_failed",
                error_message=_safe_error_message(exc),
                finished=True,
            )
            record_telemetry_event(
                session,
                trace_id=trace_id,
                task_id=task_id,
                trip_id=trip_id,
                component="worker",
                operation="task_attempt",
                status="failed",
                retry_count=max(0, attempt_count - 1),
                metadata={"error_type": type(exc).__name__},
            )
            publish_task_event(failed)
            return task_snapshot(failed)


async def _run_configured_planners(
    task_id: str,
    trip_id: str,
    payload: dict[str, Any],
    progress_callback: Any,
    *,
    review_context: ReviewContext | None = None,
) -> PlannerRunSet:
    settings = get_settings()
    primary_engine: PlannerEngine = settings.planner_engine
    review_kwargs = {"review_context": review_context} if review_context is not None else {}
    primary_call = _run_engine(
        primary_engine,
        task_id,
        trip_id,
        payload,
        progress_callback,
        **review_kwargs,
    )
    if review_context is not None or not settings.planner_compare_engines:
        return PlannerRunSet(primary=await primary_call)

    comparison_engine: PlannerEngine = "journey_graph" if primary_engine == "legacy" else "legacy"

    async def comparison_progress(*_args: Any, **_kwargs: Any) -> None:
        return None

    primary_task = asyncio.create_task(primary_call)
    comparison_task = asyncio.create_task(
        _run_engine(
            comparison_engine,
            task_id,
            trip_id,
            payload,
            comparison_progress,
        )
    )
    try:
        primary_result = await primary_task
    except BaseException:
        comparison_task.cancel()
        await asyncio.gather(comparison_task, return_exceptions=True)
        raise

    try:
        comparison_result = await comparison_task
    except asyncio.CancelledError:
        raise
    except Exception as comparison_error:
        comparison = PlannerExecution(
            engine=comparison_engine,
            client_payload={
                "success": False,
                "message": "Comparison planner failed.",
                "plan_id": task_id,
                "error_code": type(comparison_error).__name__,
            },
            schema_version="error",
        )
    else:
        comparison = comparison_result
    return PlannerRunSet(primary=primary_result, comparison=comparison)


async def _run_engine(
    engine: PlannerEngine,
    task_id: str,
    trip_id: str,
    payload: dict[str, Any],
    progress_callback: Any,
    *,
    review_context: ReviewContext | None = None,
) -> PlannerExecution:
    if engine == "legacy":
        result = await _run_legacy_planner(task_id, payload, progress_callback)
        settings = get_settings()
        return PlannerExecution(
            engine="legacy",
            client_payload=result,
            schema_version="legacy",
            model_id=settings.openai_model,
            prompt_version="legacy-unversioned",
            workflow_version="legacy-adapter/phase7",
            tool_versions={},
        )
    return await _run_journey_graph_planner(
        task_id,
        trip_id,
        payload,
        progress_callback,
        review_context=review_context,
    )


async def _run_legacy_planner(
    task_id: str,
    payload: dict[str, Any],
    progress_callback: Any,
) -> dict[str, Any]:
    """Adapt the v2 contract and invoke the existing planner without modifying it."""
    from ..agents.trip_planner_agent import get_trip_planner_agent
    from ..services.knowledge_graph_service import build_knowledge_graph

    request = (
        TripRequest.model_validate(payload["request"])
        if payload.get("contract") == "legacy"
        else _to_legacy_request(payload)
    )
    agent = get_trip_planner_agent()
    trip_plan = await agent.plan_trip(request, progress_callback=progress_callback)
    await progress_callback("graph_building", "Building knowledge graph.", 95)
    graph_data = build_knowledge_graph(trip_plan, language=request.language or "zh")
    result = TripPlanResponse(
        success=True,
        message="Trip plan generated successfully.",
        plan_id=task_id,
        data=trip_plan,
        graph_data=graph_data,
    )
    return result.model_dump(mode="json")


async def _run_journey_graph_planner(
    task_id: str,
    trip_id: str,
    payload: dict[str, Any],
    progress_callback: Any,
    *,
    review_context: ReviewContext | None = None,
) -> PlannerExecution:
    """Run or resume the typed graph and adapt its result for existing clients."""
    from langgraph.types import Command

    from ..agents.journey_graph import build_configured_plan_generator, build_journey_graph
    from ..agents.journey_graph.checkpoint import open_postgres_checkpointer
    from ..services.attraction_discovery import (
        NoopAttractionDiscoveryProvider,
        build_configured_attraction_discovery_provider,
    )
    from ..services.research import NoopWebResearchProvider, build_configured_web_research_provider
    from ..services.routing import (
        NoopRouteEstimateProvider,
        build_configured_route_estimate_provider,
    )

    request = _to_v2_request(payload)
    settings = get_settings()
    draft_generator = build_configured_plan_generator()
    research_provider = (
        NoopWebResearchProvider()
        if settings.demo_mode
        else build_configured_web_research_provider()
    )
    route_provider = (
        NoopRouteEstimateProvider()
        if settings.demo_mode
        else build_configured_route_estimate_provider()
    )
    attraction_provider = (
        NoopAttractionDiscoveryProvider()
        if settings.demo_mode
        else build_configured_attraction_discovery_provider()
    )
    node_progress = {
        "normalize_request": ("normalize_request", "Normalizing the trip request.", 12),
        "prepare_research_queries": ("prepare_research", "Preparing bounded research queries.", 20),
        "research_web": ("research_web", "Collecting source evidence.", 30),
        "collect": ("collect", "Ranking and collecting evidence.", 38),
        "plan_intercity_transport": ("transport", "Estimating intercity transport.", 46),
        "draft": ("draft", "Generating the structured itinerary draft.", 60),
        "enrich_plan": ("enrich_plan", "Building timelines and recalculating budget.", 72),
        "deterministic_validate": ("validate", "Running deterministic validators.", 80),
        "revise_plan": ("revise", "Repairing validation conflicts.", 82),
        "human_review": ("human_review", "Preparing the human review checkpoint.", 88),
        "persist": ("persist", "Persisting the approved version.", 92),
        "reject_plan": ("reject_plan", "Recording the review decision.", 92),
    }
    await progress_callback("workflow_start", "JourneyGraph workflow started.", 8)

    def observe_node(node_name: str) -> None:
        stage, message, progress = node_progress[node_name]
        asyncio.run(progress_callback(stage, message, progress))
        if settings.demo_mode and settings.demo_node_delay_seconds:
            sleep(settings.demo_node_delay_seconds)

    def invoke_graph() -> tuple[dict[str, Any], bool, bool]:
        config = {"configurable": {"thread_id": task_id}}
        model_invoked = False
        initial_state = {
            "trip_id": trip_id,
            "task_id": task_id,
            "request": request,
        }
        with open_postgres_checkpointer() as checkpointer:
            graph = build_journey_graph(
                draft_generator=draft_generator,
                research_provider=research_provider,
                attraction_provider=attraction_provider,
                route_provider=route_provider,
                checkpointer=checkpointer,
                require_human_review=True,
                node_observer=observe_node,
            )
            snapshot = graph.get_state(config)
            if snapshot.values.get("final_plan") is not None and not snapshot.next:
                state = snapshot.values
            elif review_context is not None:
                if not snapshot.next:
                    raise ValueError("The initial review checkpoint is no longer resumable.")
                state = graph.invoke(
                    Command(
                        resume={
                            "action": review_context.action,
                            "reason": review_context.reason,
                        }
                    ),
                    config,
                )
            elif snapshot.next:
                state = snapshot.values
            else:
                state = graph.invoke(initial_state, config)
                model_invoked = bool(getattr(draft_generator, "uses_provider", True))
            waiting = bool(graph.get_state(config).next)
        return dict(state), waiting, model_invoked

    started = perf_counter()
    state, waiting, model_invoked = await asyncio.to_thread(invoke_graph)
    graph_latency_ms = round((perf_counter() - started) * 1000)
    plan = TripPlanV2.model_validate(state.get("final_plan") or state["draft_plan"])
    client_response = await _build_client_payload(task_id, request, plan, progress_callback)
    workflow_status: Literal["completed", "awaiting_approval", "rejected"] = "completed"
    if waiting:
        workflow_status = "awaiting_approval"
    elif state.get("approval_status") == "rejected":
        workflow_status = "rejected"
    return PlannerExecution(
        engine="journey_graph",
        client_payload=client_response,
        schema_version=plan.schema_version,
        native_payload=plan.model_dump(mode="json"),
        source_evidence=tuple(plan.source_evidence),
        workflow_status=workflow_status,
        review_workflow_type="initial",
        review_thread_id=task_id,
        review_proposed_version=1,
        review_reason=(review_context.reason if review_context else "Initial plan review"),
        validation_report=plan.validation_report.model_dump(mode="json"),
        model_id=(
            state.get("metrics", {}).get("model_generation", {}).get("model_id")
            or getattr(draft_generator, "model_id", settings.openai_model)
        ),
        prompt_version=PROMPT_VERSION,
        workflow_version=WORKFLOW_VERSION,
        tool_versions=TOOL_VERSIONS,
        metrics={
            **state.get("metrics", {}),
            "graph_latency_ms": graph_latency_ms,
            "model_invoked": model_invoked,
        },
    )


async def _run_replan_planner(
    task_id: str,
    trip_id: str,
    payload: dict[str, Any],
    progress_callback: Any,
    review_context: ReviewContext,
) -> PlannerExecution:
    """Start or resume the dedicated scoped Replan Graph."""
    from langgraph.types import Command

    from ..agents.journey_graph.checkpoint import open_postgres_checkpointer
    from ..agents.replan_graph import build_replan_graph
    from ..services.research import build_configured_web_research_provider
    from ..services.routing import build_configured_route_estimate_provider

    request = _to_v2_request(payload)
    await progress_callback("replanning", "Scoped Replan Graph started.", 82)

    def load_base_plan() -> TripPlanV2:
        if review_context.native_payload is not None:
            return TripPlanV2.model_validate(review_context.native_payload)
        with SessionLocal() as session:
            version = (
                get_trip_version(session, trip_id, review_context.base_version)
                if review_context.base_version is not None
                else get_active_trip_version(session, trip_id)
            )
            if version is None or version.native_payload is None:
                raise ValueError("The requested base version cannot be replanned.")
            return TripPlanV2.model_validate(version.native_payload)

    base_plan = load_base_plan()
    change_request = ReplanRequestV2.model_validate(review_context.change_request)

    def invoke_graph() -> tuple[dict[str, Any], bool]:
        config = {"configurable": {"thread_id": review_context.thread_id}}
        initial_state = {
            "trip_id": trip_id,
            "task_id": task_id,
            "thread_id": review_context.thread_id,
            "request": request,
            "original_plan": base_plan,
            "base_plan": base_plan,
            "change_request": change_request,
            "from_version": review_context.base_version,
            "proposed_version": review_context.proposed_version or 1,
            "replan_round": 0,
        }
        with open_postgres_checkpointer() as checkpointer:
            graph = build_replan_graph(
                research_provider=build_configured_web_research_provider(),
                route_provider=build_configured_route_estimate_provider(),
                checkpointer=checkpointer,
                require_human_review=True,
            )
            snapshot = graph.get_state(config)
            if review_context.status == "requested":
                state = snapshot.values if snapshot.next else graph.invoke(initial_state, config)
            elif review_context.status in {"approved", "changes_requested", "rejected"}:
                if not snapshot.next:
                    raise ValueError("The replan review checkpoint is no longer resumable.")
                resume: dict[str, Any] = {
                    "action": review_context.action,
                    "reason": review_context.reason,
                }
                if review_context.action == "modify":
                    resume["changes"] = review_context.change_request
                state = graph.invoke(Command(resume=resume), config)
            else:
                state = snapshot.values
            waiting = bool(graph.get_state(config).next)
        return dict(state), waiting

    started = perf_counter()
    state, waiting = await asyncio.to_thread(invoke_graph)
    graph_latency_ms = round((perf_counter() - started) * 1000)
    plan = TripPlanV2.model_validate(state.get("final_plan") or state["draft_plan"])
    client_response = await _build_client_payload(task_id, request, plan, progress_callback)
    workflow_status: Literal["completed", "awaiting_approval", "rejected"] = "completed"
    if waiting:
        workflow_status = "awaiting_approval"
    elif state.get("review_action") == "reject":
        workflow_status = "rejected"
    diff = state.get("diff")
    scope = state.get("impact_scope")
    return PlannerExecution(
        engine="journey_graph",
        client_payload=client_response,
        schema_version=plan.schema_version,
        native_payload=plan.model_dump(mode="json"),
        source_evidence=tuple(plan.source_evidence),
        workflow_status=workflow_status,
        review_workflow_type="replan",
        review_thread_id=review_context.thread_id,
        review_base_version=review_context.base_version,
        review_proposed_version=review_context.proposed_version,
        review_reason=review_context.reason,
        impact_scope=(scope.model_dump(mode="json") if scope is not None else None),
        diff_payload=(diff.model_dump(mode="json") if diff is not None else {}),
        validation_report=plan.validation_report.model_dump(mode="json"),
        refreshed_sources=tuple(state.get("refreshed_sources", [])),
        model_id=get_settings().openai_model,
        prompt_version=PROMPT_VERSION,
        workflow_version=WORKFLOW_VERSION,
        tool_versions=TOOL_VERSIONS,
        metrics={
            **state.get("metrics", {}),
            "graph_latency_ms": graph_latency_ms,
            "model_invoked": False,
        },
    )


async def _build_client_payload(
    task_id: str,
    request: TripRequestV2,
    native_plan: TripPlanV2,
    progress_callback: Any,
) -> dict[str, Any]:
    from ..adapters import trip_plan_v2_to_legacy
    from ..services.knowledge_graph_service import build_knowledge_graph

    adapted_plan = trip_plan_v2_to_legacy(native_plan)
    await progress_callback("graph_building", "Building knowledge graph.", 88)
    graph_data = build_knowledge_graph(adapted_plan, language=request.language)
    return TripPlanResponse(
        success=True,
        message="Trip plan proposal generated successfully.",
        plan_id=task_id,
        data=adapted_plan,
        graph_data=graph_data,
    ).model_dump(mode="json")


def _to_v2_request(payload: dict[str, Any]) -> TripRequestV2:
    if payload.get("contract") != "legacy":
        return TripRequestV2.model_validate(payload)

    legacy = TripRequest.model_validate(payload["request"])
    destinations = [
        {"city": destination.city, "days": destination.days} for destination in legacy.cities
    ]
    return TripRequestV2(
        origin=legacy.origin or legacy.city,
        destinations=destinations,
        start_date=legacy.start_date,
        end_date=legacy.end_date,
        travel_days=legacy.travel_days,
        transport_preferences=[legacy.transportation] if legacy.transportation else [],
        accommodation_preference=legacy.accommodation,
        interests=legacy.preferences,
        free_text_input=legacy.free_text_input or "",
        language=legacy.language or "zh",
        timezone="Asia/Shanghai",
    )


def _to_legacy_request(payload: dict[str, Any]) -> TripRequest:
    destinations = payload["destinations"]
    context = list(payload.get("avoid", [])) + list(payload.get("accessibility_needs", []))
    if payload.get("budget_total"):
        context.append(f"Budget: {payload['budget_total']} {payload.get('currency', 'CNY')}")
    free_text = payload.get("free_text_input", "")
    if context:
        free_text = "\n".join(filter(None, [free_text, "Constraints: " + "; ".join(context)]))
    return TripRequest(
        origin=payload["origin"],
        city=destinations[0]["city"],
        cities=[CityStay(city=item["city"], days=item["days"]) for item in destinations],
        start_date=payload["start_date"],
        end_date=payload["end_date"],
        travel_days=payload["travel_days"],
        transportation=", ".join(payload.get("transport_preferences", [])) or "public transit",
        accommodation=payload.get("accommodation_preference") or "midscale hotel",
        preferences=list(payload.get("interests", [])) + list(payload.get("must_visit", [])),
        free_text_input=free_text,
        language=payload.get("language", "zh"),
    )


def _usage_summary(metrics: dict[str, Any] | None) -> dict[str, Any]:
    """Extract stable numeric usage fields for an immutable version manifest."""
    generation = (metrics or {}).get("model_generation", {})
    return {
        key: generation.get(key, 0)
        for key in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "model_cost_usd",
            "latency_ms",
            "retry_count",
        )
    }


def _persist_execution_telemetry(
    session: Any,
    *,
    trace_id: str,
    task_id: str,
    trip_id: str,
    execution: PlannerExecution,
) -> None:
    metrics = execution.metrics or {}
    generation = metrics.get("model_generation", {})
    model_invoked = execution.engine == "legacy" or bool(metrics.get("model_invoked"))
    event_generation = generation if model_invoked else {}
    record_telemetry_event(
        session,
        trace_id=trace_id,
        task_id=task_id,
        trip_id=trip_id,
        component="planner",
        operation="engine_run" if model_invoked else "engine_resume",
        status=event_generation.get("status", "completed"),
        node="draft" if execution.engine == "journey_graph" else "legacy_planner",
        latency_ms=int(metrics.get("graph_latency_ms", generation.get("latency_ms", 0)) or 0),
        input_tokens=int(event_generation.get("input_tokens", 0) or 0),
        output_tokens=int(event_generation.get("output_tokens", 0) or 0),
        total_tokens=int(event_generation.get("total_tokens", 0) or 0),
        model_cost_usd=float(event_generation.get("model_cost_usd", 0) or 0),
        retry_count=int(event_generation.get("retry_count", 0) or 0),
        model_id=execution.model_id,
        prompt_version=execution.prompt_version,
        workflow_version=execution.workflow_version,
        metadata=sanitize_metadata(
            {
                "engine": execution.engine,
                "schema_version": execution.schema_version,
                "workflow_status": execution.workflow_status,
            }
        ),
    )
    for provider_call in metrics.get("research_provider_calls", []):
        provider = str(provider_call.get("provider", "unknown"))[:120]
        record_telemetry_event(
            session,
            trace_id=trace_id,
            task_id=task_id,
            trip_id=trip_id,
            component="tool",
            operation="research_provider_call",
            status="completed" if provider_call.get("success") else "failed",
            node="research",
            tool=provider,
            latency_ms=int(provider_call.get("latency_ms", 0) or 0),
            cache_hit=bool(provider_call.get("cache_hit", False)),
            workflow_version=execution.workflow_version,
            tool_version=(execution.tool_versions or {}).get("web_research"),
            metadata=sanitize_metadata(
                {
                    "error_code": provider_call.get("error_code"),
                    "query_id": provider_call.get("query_id"),
                }
            ),
        )


def _safe_error_message(exc: Exception) -> str:
    text = str(exc).strip() or type(exc).__name__
    settings = get_settings()
    known_secrets = {
        settings.openai_api_key,
        settings.google_maps_api_key,
        settings.xhs_cookie,
        os.getenv("LLM_API_KEY", ""),
        os.getenv("OPENAI_API_KEY", ""),
    }
    for secret in sorted(known_secrets, key=len, reverse=True):
        if len(secret) >= 8:
            text = text.replace(secret, _REDACTED)

    text = _URL_CREDENTIAL_PATTERN.sub(rf"\1{_REDACTED}@", text)
    text = _AUTH_VALUE_PATTERN.sub(rf"\1 {_REDACTED}", text)
    text = _SECRET_ASSIGNMENT_PATTERN.sub(rf"\1\2{_REDACTED}", text)
    text = _PROVIDER_TOKEN_PATTERN.sub(_REDACTED, text)
    return text[:1000]


def _renew_lock(lock: Any, lock_timeout: int, stop: threading.Event, task_id: str) -> None:
    """Keep a live worker lock fresh while allowing fast expiry after process death."""
    interval = max(1.0, lock_timeout / 3)
    while not stop.wait(interval):
        try:
            lock.extend(lock_timeout, replace_ttl=True)
        except Exception:
            LOGGER.warning("Unable to renew task lock for %s", task_id)


def _execution_lock_active(task_id: str) -> bool:
    """Return whether another worker still owns the renewable execution lock."""
    client = Redis.from_url(
        redis_url(),
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        return bool(client.exists(f"journeyops:task-lock:{task_id}"))
    finally:
        client.close()
