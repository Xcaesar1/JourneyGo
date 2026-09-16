"""Typed task models for the durable v2 trip API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .review_models import TripReviewRecordV2

TRIP_TASK_RECORD_V2_EXAMPLE: dict[str, Any] = {
    "task_id": "task_1234567890ab",
    "trip_id": "trip_1234567890ab",
    "trace_id": "trace_1234567890abcdef",
    "status": "queued",
    "stage": "queued",
    "progress": 0,
    "attempt_count": 0,
    "max_attempts": 3,
    "created_at": "2026-08-06T00:00:00Z",
    "updated_at": "2026-08-06T00:00:00Z",
    "started_at": None,
    "finished_at": None,
    "message": "Task queued for durable execution.",
    "result": None,
    "review": None,
    "error": None,
}

TaskStatusV2 = Literal[
    "queued",
    "processing",
    "retrying",
    "awaiting_approval",
    "cancel_requested",
    "cancelled",
    "completed",
    "rejected",
    "failed",
]


class TaskErrorV2(BaseModel):
    """Sanitized terminal task error."""

    code: str
    message: str


class TripTaskRecordV2(BaseModel):
    """Durable task state returned by v2 task endpoints."""

    model_config = ConfigDict(json_schema_extra={"example": TRIP_TASK_RECORD_V2_EXAMPLE})

    task_id: str = Field(..., description="Durable task identifier.")
    trip_id: str = Field(..., description="Durable trip identifier.")
    trace_id: str = Field(..., description="Correlation identifier spanning API, worker, nodes, and tools.")
    status: TaskStatusV2
    stage: str
    progress: int = Field(..., ge=0, le=100)
    attempt_count: int = Field(..., ge=0)
    max_attempts: int = Field(..., ge=1)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str
    result: dict[str, Any] | None = None
    review: TripReviewRecordV2 | None = None
    error: TaskErrorV2 | None = None
