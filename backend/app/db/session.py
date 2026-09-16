"""SQLAlchemy engine and request-scoped session helpers."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = "postgresql+psycopg://journeyops:journeyops@localhost:5432/journeyops"


def database_url() -> str:
    """Return the configured database URL without logging credentials."""
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def build_engine(url: str | None = None) -> Engine:
    """Build a pool-pre-ping SQLAlchemy engine."""
    return create_engine(url or database_url(), pool_pre_ping=True)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield one SQLAlchemy session per API request."""
    with SessionLocal() as session:
        yield session
