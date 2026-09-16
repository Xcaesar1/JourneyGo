"""Canonical task resource aliases required by the API v2 contract."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, WebSocket, status
from sqlalchemy.orm import Session

from ...db.session import get_db_session
from ...domain.observability_models import TelemetryEventV2
from ...domain.task_models import TripTaskRecordV2
from . import trips

router = APIRouter(prefix="/tasks", tags=["API v2 tasks"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("/{task_id}", response_model=TripTaskRecordV2, summary="Read durable task status")
def read_task(task_id: str, session: DbSession) -> TripTaskRecordV2:
    return trips.read_task(task_id, session)


@router.get(
    "/{task_id}/events",
    response_model=list[TelemetryEventV2],
    summary="Read persisted task events",
)
def read_task_events(task_id: str, session: DbSession) -> list[TelemetryEventV2]:
    """Return persisted, sanitized events; Redis Pub/Sub remains transient."""
    return trips.read_task_telemetry(task_id, session)


@router.post(
    "/{task_id}/cancel",
    response_model=TripTaskRecordV2,
    summary="Cancel a queued or running task",
)
def cancel_task(task_id: str, session: DbSession) -> TripTaskRecordV2:
    return trips.cancel_task(task_id, session)


@router.post(
    "/{task_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TripTaskRecordV2,
    summary="Retry a failed or cancelled task",
)
def retry_task(task_id: str, session: DbSession, request: Request) -> TripTaskRecordV2:
    return trips.retry_task(task_id, session, request)


@router.websocket("/{task_id}/ws")
async def task_events(websocket: WebSocket, task_id: str) -> None:
    await trips.task_events(websocket, task_id)
