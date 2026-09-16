"""Canonical trip resource contracts for the public API v2 surface."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .task_models import TripTaskRecordV2
from .trip_models import TripRequestV2


class TripResourceV2(BaseModel):
    """Canonical trip request, durable task, and active-version pointer."""

    model_config = ConfigDict(extra="forbid")

    trip_id: str
    request: TripRequestV2
    task: TripTaskRecordV2
    active_version: int | None = Field(default=None, ge=1)
    created_at: datetime
    updated_at: datetime
