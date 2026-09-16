"""Trace propagation, version manifests, cost calculation, and safe metadata."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request

PROMPT_VERSION = "trip-plan-v2/2026-08-08"
WORKFLOW_VERSION = "journey-graph/phase7"
TOOL_VERSIONS = {
    "web_research": "2.0",
    "route_estimator": "2.0",
    "community_research": "1.0",
    "deterministic_validator": "2.0",
}
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,64}$")
_SECRET_KEYS = ("key", "token", "secret", "password", "authorization", "cookie", "prompt", "payload")


def new_trace_id() -> str:
    return f"trace_{uuid4().hex}"


def normalize_trace_id(value: str | None) -> str:
    """Accept a bounded caller trace or issue a new opaque identifier."""
    candidate = (value or "").strip()
    return candidate if _TRACE_PATTERN.fullmatch(candidate) else new_trace_id()


def install_trace_middleware(app: FastAPI) -> None:
    """Correlate API responses without exposing request bodies or headers."""

    @app.middleware("http")
    async def trace_requests(request: Request, call_next):
        trace_id = normalize_trace_id(request.headers.get("X-Trace-ID"))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response


def sanitize_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    """Keep scalar operational fields and redact credential-like keys recursively."""
    result: dict[str, Any] = {}
    for key, item in (value or {}).items():
        lowered = key.casefold()
        if any(marker in lowered for marker in _SECRET_KEYS):
            result[key] = "[REDACTED]"
        elif isinstance(item, dict):
            result[key] = sanitize_metadata(item)
        elif isinstance(item, list):
            result[key] = [
                sanitize_metadata(entry) if isinstance(entry, dict) else entry
                for entry in item[:50]
            ]
        elif isinstance(item, (str, int, float, bool)) or item is None:
            result[key] = item
    return result


def calculate_model_cost(
    input_tokens: int,
    output_tokens: int,
    *,
    input_per_million_usd: float,
    output_per_million_usd: float,
) -> float:
    return round(
        (input_tokens / 1_000_000) * input_per_million_usd
        + (output_tokens / 1_000_000) * output_per_million_usd,
        8,
    )
