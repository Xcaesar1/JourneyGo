"""Process and local-dependency health endpoints."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from redis import Redis
from sqlalchemy import text

from ..db.session import SessionLocal
from ..services.task_events import redis_url

router = APIRouter(tags=["health"])
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _data_directory_check() -> dict[str, object]:
    """Inspect the persistent data directory without writing to it."""
    exists = DATA_DIR.is_dir()
    readable = exists and os.access(DATA_DIR, os.R_OK | os.X_OK)
    writable = exists and os.access(DATA_DIR, os.W_OK)
    ready = bool(exists and readable and writable)
    return {
        "status": "ready" if ready else "not_ready",
        "exists": exists,
        "readable": readable,
        "writable": writable,
    }


def _database_check() -> dict[str, str]:
    """Verify PostgreSQL connectivity with a read-only scalar query."""
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        return {"status": "not_ready", "reason": type(exc).__name__}


def _redis_check() -> dict[str, str]:
    """Verify the Redis broker/event transport without logging its URL."""
    client = Redis.from_url(redis_url(), socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
        return {"status": "ready"}
    except Exception as exc:
        return {"status": "not_ready", "reason": type(exc).__name__}
    finally:
        client.close()


@router.get("/health/live")
async def health_live():
    """Report only whether the API process can serve requests."""
    return {"status": "alive", "service": "tripstar-api"}


@router.get("/health/ready")
async def health_ready():
    """Require writable data storage, PostgreSQL, and Redis."""
    data_directory = _data_directory_check()
    database = _database_check()
    redis = _redis_check()
    checks = {
        "data_directory": data_directory,
        "database": database,
        "redis": redis,
    }
    ready = all(check["status"] == "ready" for check in checks.values())
    payload = {
        "status": "ready" if ready else "not_ready",
        "service": "tripstar-api",
        "checks": checks,
    }
    if payload["status"] != "ready":
        raise HTTPException(status_code=503, detail=payload)
    return payload
