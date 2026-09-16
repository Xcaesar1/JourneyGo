"""Legacy trip API contracts backed by the Phase 2 durable task architecture."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...db.models import TripTask
from ...db.repository import (
    IdempotencyConflictError,
    attach_celery_task,
    create_or_get_task,
    get_task,
    update_task_state,
)
from ...db.session import SessionLocal, get_db_session
from ...models.schemas import TripRequest
from ...services.guardrails import enforce_spend_guardrails
from ...services.task_events import (
    TASK_STREAM_STOP_STATUSES,
    publish_task_event,
    redis_url,
    task_channel,
)
from ...workers.trip_tasks import enqueue_trip_task

router = APIRouter(prefix="/trip", tags=["旅行规划"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "/plan",
    summary="提交旅行规划任务",
    description=(
        "保留原响应契约，任务先写 PostgreSQL，再由 Celery Worker 调用已配置的 Planner。"
    ),
)
def plan_trip(
    request: TripRequest,
    session: DbSession,
    http_request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, Any]:
    """Submit a legacy request without using process memory or JSON task files."""
    payload = {
        "contract": "legacy",
        "request": request.model_dump(mode="json"),
    }
    enforce_spend_guardrails(http_request, session, payload)
    key = _legacy_idempotency_key(payload, idempotency_key)
    try:
        task, created = create_or_get_task(
            session,
            request_payload=payload,
            idempotency_key=key,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail="幂等键已用于不同的请求内容") from exc
    if created:
        task = _dispatch_or_fail(session, task)
    publish_task_event(task)
    return {
        "task_id": task.id,
        "plan_id": task.id,
        "status": "processing",
        "ws_url": f"/api/trip/ws/{task.id}",
        "message": f"任务已提交，可通过 WebSocket /api/trip/ws/{task.id} 实时订阅状态",
    }


@router.websocket("/ws/{task_id}")
async def trip_task_ws(websocket: WebSocket, task_id: str) -> None:
    """Translate Redis Pub/Sub snapshots into the unchanged legacy event shape."""
    await websocket.accept()
    redis_client = AsyncRedis.from_url(redis_url(), decode_responses=True)
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(task_channel(task_id))
        with SessionLocal() as session:
            task = get_task(session, task_id)
            if task is None:
                await websocket.send_json(
                    {
                        "task_id": task_id,
                        "plan_id": task_id,
                        "status": "failed",
                        "stage": "failed",
                        "progress": 100,
                        "message": "任务不存在",
                        "error": "任务不存在",
                    }
                )
                await websocket.close(code=1008)
                return
            snapshot = _legacy_event(task)

        await websocket.send_json(snapshot)
        if task.status in TASK_STREAM_STOP_STATUSES:
            await websocket.close()
            return

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is not None:
                with SessionLocal() as session:
                    current = get_task(session, task_id)
                    if current is None:
                        break
                    event = _legacy_event(current)
                await websocket.send_json(event)
                if current.status in TASK_STREAM_STOP_STATUSES:
                    break
            else:
                with SessionLocal() as session:
                    current = get_task(session, task_id)
                    if current is None:
                        break
                    if current.status in TASK_STREAM_STOP_STATUSES:
                        await websocket.send_json(_legacy_event(current))
                        break
    except WebSocketDisconnect:
        return
    finally:
        await pubsub.aclose()
        await redis_client.aclose()


@router.get(
    "/history",
    summary="最近历史计划",
    description="从 PostgreSQL 返回最近成功生成的计划摘要。",
)
def get_trip_history(session: DbSession, limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    """Build legacy history cards from durable task results."""
    safe_limit = max(1, min(int(limit or 10), 50))
    tasks = session.scalars(
        select(TripTask)
        .options(selectinload(TripTask.trip))
        .where(TripTask.status == "completed")
        .order_by(TripTask.updated_at.desc())
        .limit(safe_limit)
    )
    return {"items": [_history_item(task) for task in tasks]}


@router.get(
    "/status/{task_id}",
    summary="查询任务状态",
    description="保留旧客户端使用的轮询响应结构，事实来源为 PostgreSQL。",
)
def get_task_status(task_id: str, session: DbSession) -> dict[str, Any]:
    """Return the original polling contract from a durable row."""
    task = get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status == "completed":
        return {
            "task_id": task.id,
            "plan_id": task.id,
            "status": "completed",
            "result": task.result_payload,
        }
    if task.status == "awaiting_approval":
        return {
            "task_id": task.id,
            "plan_id": task.id,
            "status": "awaiting_approval",
            "stage": task.stage,
            "progress": task.progress,
            "result": task.result_payload,
            "review": task.review_payload,
        }
    if task.status in {"failed", "cancelled", "rejected"}:
        return {
            "task_id": task.id,
            "plan_id": task.id,
            "status": "failed",
            "error": task.error_message or task.message,
            "request_payload": _legacy_request_payload(task),
        }
    return {
        "task_id": task.id,
        "plan_id": task.id,
        "status": "processing",
        "stage": task.stage,
        "progress": task.progress,
        "progress_text": task.message,
    }


@router.get("/health", summary="旅行规划服务健康检查")
def health_check(session: DbSession) -> dict[str, str]:
    """Confirm that the legacy adapter can access its durable task store."""
    session.execute(select(1))
    return {"status": "healthy", "service": "trip-planner"}


def _dispatch_or_fail(session: Session, task: TripTask) -> TripTask:
    try:
        broker_task_id = enqueue_trip_task(task.id)
    except Exception as exc:
        failed = update_task_state(
            session,
            task.id,
            status="failed",
            stage="dispatch_failed",
            message="任务投递失败",
            error_code="dispatch_failed",
            error_message=type(exc).__name__,
            finished=True,
        )
        publish_task_event(failed)
        raise HTTPException(status_code=503, detail="任务队列暂不可用") from exc

    try:
        return attach_celery_task(session, task.id, broker_task_id)
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail="任务已投递但确认失败，等待自动恢复") from exc


def _legacy_event(task: TripTask) -> dict[str, Any]:
    if task.status == "completed":
        status = "completed"
    elif task.status == "awaiting_approval":
        status = "awaiting_approval"
    elif task.status in {"failed", "cancelled", "rejected"}:
        status = "failed"
    else:
        status = "processing"
    event: dict[str, Any] = {
        "task_id": task.id,
        "plan_id": task.id,
        "status": status,
        "stage": task.stage,
        "progress": task.progress,
        "message": task.message,
    }
    if status == "failed":
        event["error"] = task.error_message or task.message
        event["request_payload"] = _legacy_request_payload(task)
    if task.result_payload is not None:
        event["result"] = task.result_payload
    if task.review_payload is not None:
        event["review"] = task.review_payload
    return event


def _history_item(task: TripTask) -> dict[str, Any]:
    result = task.result_payload or {}
    plan = result.get("data") or {}
    request = _legacy_request_payload(task)
    return {
        "plan_id": task.id,
        "task_id": task.id,
        "city": plan.get("city") or request.get("city", ""),
        "start_date": plan.get("start_date") or request.get("start_date", ""),
        "end_date": plan.get("end_date") or request.get("end_date", ""),
        "travel_days": request.get("travel_days") or len(plan.get("days", [])),
        "updated_at": task.updated_at.isoformat(),
        "overall_suggestions": plan.get("overall_suggestions", ""),
    }


def _legacy_request_payload(task: TripTask) -> dict[str, Any]:
    payload = task.trip.request_payload
    if payload.get("contract") == "legacy":
        return payload.get("request", {})
    return payload


def _legacy_idempotency_key(payload: dict[str, Any], supplied_key: str | None) -> str:
    if supplied_key is not None and len(supplied_key) > 256:
        raise HTTPException(status_code=400, detail="Idempotency-Key 过长")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    namespace = f"legacy-header:{supplied_key}" if supplied_key else f"legacy:{uuid4()}:{canonical}"
    return hashlib.sha256(namespace.encode("utf-8")).hexdigest()
