"""Shared pytest fixtures for backend contract and durable task tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.app.api.errors import register_api_exception_handlers
from backend.app.api.routes import trip as legacy_trip_routes
from backend.app.api.v2 import tasks as v2_task_routes
from backend.app.api.v2 import trips as v2_trip_routes
from backend.app.db.base import Base
from backend.app.db.session import get_db_session
from backend.app.services.observability import install_trace_middleware
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def tasks_dir(tmp_path: Path) -> Path:
    """Retained as a generic temp directory for legacy fixture compatibility."""
    return tmp_path


@pytest.fixture
def db_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def api_app(
    tasks_dir: Path,
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    _ = tasks_dir
    dispatch_counter = {"value": 0}

    def fake_dispatch(_: str) -> str:
        dispatch_counter["value"] += 1
        return f"celery-test-{dispatch_counter['value']}"

    monkeypatch.setattr(v2_trip_routes, "enqueue_trip_task", fake_dispatch)
    monkeypatch.setattr(v2_trip_routes, "publish_task_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(legacy_trip_routes, "enqueue_trip_task", fake_dispatch)
    monkeypatch.setattr(legacy_trip_routes, "publish_task_event", lambda *_args, **_kwargs: None)
    app = FastAPI()
    register_api_exception_handlers(app)
    install_trace_middleware(app)
    app.include_router(legacy_trip_routes.router, prefix="/api")
    app.include_router(v2_trip_routes.router, prefix="/api/v2")
    app.include_router(v2_task_routes.router, prefix="/api/v2")

    def override_db_session():
        with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session

    @app.get("/api/v2/_test/unhandled", include_in_schema=False)
    async def raise_unhandled_v2_error() -> None:
        raise RuntimeError("test-only failure")

    return app


@pytest.fixture
def client(api_app: FastAPI) -> TestClient:
    with TestClient(api_app, raise_server_exceptions=False) as test_client:
        yield test_client
