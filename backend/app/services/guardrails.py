"""Cost-bearing API guardrails with no credential or prompt logging."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import time
from typing import Any

from fastapi import HTTPException, Request
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db.models import TripTask
from .observability import calculate_model_cost
from .task_events import redis_url

_ACTIVE_STATUSES = ("queued", "processing", "retrying", "cancel_requested")
_INJECTION_PATTERNS = (
    re.compile(r"(?i)\bignore\s+(all\s+)?(previous|prior|system|developer)\s+instructions?\b"),
    re.compile(r"(?i)\b(reveal|show|print|exfiltrate)\b.{0,60}\b(system prompt|api key|secret|token)\b"),
    re.compile(r"(?i)<\s*(system|developer|assistant)\s*>"),
    re.compile(r"忽略.{0,20}(之前|以上|系统|开发者).{0,12}(指令|提示)"),
    re.compile(r"(泄露|显示|输出).{0,30}(系统提示词|密钥|令牌|密码)"),
)


def enforce_spend_guardrails(
    request: Request,
    session: Session,
    payload: dict[str, Any],
) -> None:
    """Protect endpoints that can enqueue or resume model work."""
    settings = get_settings()
    _require_access_code(request, settings)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > settings.api_max_request_bytes:
        raise HTTPException(status_code=413, detail="Request body exceeds the configured limit.")
    _reject_prompt_injection(payload)
    _enforce_token_and_cost_budget(serialized, settings)
    _enforce_concurrency(session, settings)
    if settings.api_rate_limit_enabled:
        _consume_rate_limit(request, settings)


def _require_access_code(request: Request, settings: Settings) -> None:
    if not settings.api_access_code_required:
        return
    configured = settings.api_access_code.get_secret_value()
    if not configured:
        raise HTTPException(status_code=503, detail="API access protection is not configured.")
    supplied = request.headers.get("X-Access-Code", "")
    if not hmac.compare_digest(supplied.encode(), configured.encode()):
        raise HTTPException(status_code=401, detail="A valid API access code is required.")


def _consume_rate_limit(request: Request, settings: Settings) -> None:
    supplied = request.headers.get("X-Access-Code", "")
    client_host = request.client.host if request.client else "unknown"
    identity_digest = hashlib.sha256((supplied or client_host).encode()).hexdigest()[:32]
    route_digest = hashlib.sha256(request.url.path.encode()).hexdigest()[:16]
    window = settings.api_rate_limit_window_seconds
    bucket = int(time.time()) // window
    key = f"journeyops:rate:{route_digest}:{identity_digest}:{bucket}"
    client = Redis.from_url(redis_url(), decode_responses=True)
    try:
        pipeline = client.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, window + 1)
        count, _ = pipeline.execute()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Rate-limit service is unavailable.") from exc
    finally:
        client.close()
    if int(count) > settings.api_rate_limit_requests:
        raise HTTPException(status_code=429, detail="API rate limit exceeded.")


def _enforce_concurrency(session: Session, settings: Settings) -> None:
    active = session.scalar(
        select(func.count()).select_from(TripTask).where(TripTask.status.in_(_ACTIVE_STATUSES))
    )
    if int(active or 0) >= settings.api_max_active_trip_tasks:
        raise HTTPException(status_code=429, detail="Active trip task limit reached.")


def _enforce_token_and_cost_budget(serialized: str, settings: Settings) -> None:
    estimated_input_tokens = max(1, math.ceil(len(serialized) / 4))
    attempts = settings.llm_structured_max_attempts
    estimated_total_tokens = attempts * (
        estimated_input_tokens + settings.llm_structured_max_tokens
    )
    if estimated_total_tokens > settings.llm_max_tokens_per_trip:
        raise HTTPException(status_code=429, detail="Model token budget exceeded.")
    estimated_cost = attempts * calculate_model_cost(
        estimated_input_tokens,
        settings.llm_structured_max_tokens,
        input_per_million_usd=settings.llm_input_cost_per_million_usd,
        output_per_million_usd=settings.llm_output_cost_per_million_usd,
    )
    if estimated_cost > settings.llm_max_cost_per_trip_usd:
        raise HTTPException(status_code=429, detail="Model cost budget exceeded.")


def _reject_prompt_injection(value: Any) -> None:
    for text in _iter_text(value):
        if any(pattern.search(text) for pattern in _INJECTION_PATTERNS):
            raise HTTPException(
                status_code=422,
                detail="Input contains an unsafe instruction-override pattern.",
            )


def _iter_text(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_text(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_text(item)
