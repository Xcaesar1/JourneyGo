"""Redis event transport for durable task progress."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

from redis import Redis

from ..db.models import TripTask

LOGGER = logging.getLogger(__name__)
FINAL_TASK_STATUSES = frozenset({"completed", "rejected", "failed", "cancelled"})
TASK_STREAM_STOP_STATUSES = FINAL_TASK_STATUSES | {"awaiting_approval"}


def redis_url() -> str:
    """Return the Redis URL without exposing it in logs."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


def task_channel(task_id: str) -> str:
    """Return the isolated Pub/Sub channel for one task."""
    return f"journeyops:trip-task:{task_id}"


def task_snapshot(task: TripTask) -> dict[str, Any]:
    """Serialize a database task into the public v2 response shape."""
    return {
        "task_id": task.id,
        "trip_id": task.trip_id,
        "trace_id": task.trace_id,
        "status": task.status,
        "stage": task.stage,
        "progress": task.progress,
        "message": task.message,
        "attempt_count": task.attempt_count,
        "max_attempts": task.max_attempts,
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
        "started_at": _iso(task.started_at),
        "finished_at": _iso(task.finished_at),
        "result": task.result_payload,
        "review": task.review_payload,
        "error": (
            {"code": task.error_code or "task_failed", "message": task.error_message or task.message}
            if task.status == "failed"
            else None
        ),
    }


def publish_task_event(task: TripTask, client: Redis | None = None) -> None:
    """Publish a best-effort snapshot; PostgreSQL remains the source of truth."""
    owns_client = client is None
    redis_client = client or Redis.from_url(redis_url(), decode_responses=True)
    try:
        redis_client.publish(task_channel(task.id), json.dumps(task_snapshot(task), ensure_ascii=False))
    except Exception as exc:  # Pub/Sub loss must not roll back durable state.
        LOGGER.warning("Unable to publish task event: %s", type(exc).__name__)
    finally:
        if owns_client:
            redis_client.close()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
