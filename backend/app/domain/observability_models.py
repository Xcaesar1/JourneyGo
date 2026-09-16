"""Public sanitized telemetry contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TelemetryEventV2(BaseModel):
    """One bounded event without prompts, credentials, or generated payloads."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    task_id: str
    trip_id: str
    component: str
    operation: str
    status: str
    node: str | None = None
    tool: str | None = None
    latency_ms: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    model_cost_usd: float = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    cache_hit: bool | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    workflow_version: str | None = None
    tool_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
