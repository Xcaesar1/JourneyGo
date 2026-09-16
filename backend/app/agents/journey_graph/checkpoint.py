"""Secure PostgreSQL checkpointer lifecycle for JourneyGraph."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row

from ...db.session import database_url

ALLOWED_CHECKPOINT_TYPES = [
    ("backend.app.domain.research_models", "CommunityResearchResult"),
    ("backend.app.domain.research_models", "ProviderCallMetric"),
    ("backend.app.domain.research_models", "ProviderIssue"),
    ("backend.app.domain.research_models", "ResearchQuery"),
    ("backend.app.domain.research_models", "ResearchReport"),
    ("backend.app.domain.research_models", "SourceEvidence"),
    ("backend.app.domain.research_models", "WebSearchResult"),
    ("backend.app.domain.review_models", "ImpactScopeV2"),
    ("backend.app.domain.review_models", "PlanDiffEntryV2"),
    ("backend.app.domain.review_models", "PlanDiffV2"),
    ("backend.app.domain.review_models", "ReplanRequestV2"),
    ("backend.app.domain.trip_models", "AttractionV2"),
    ("backend.app.domain.trip_models", "BudgetV2"),
    ("backend.app.domain.trip_models", "CityStayV2"),
    ("backend.app.domain.trip_models", "DayPlanV2"),
    ("backend.app.domain.trip_models", "HotelV2"),
    ("backend.app.domain.trip_models", "IntercityTransportOptionV2"),
    ("backend.app.domain.trip_models", "LocationV2"),
    ("backend.app.domain.trip_models", "MealV2"),
    ("backend.app.domain.trip_models", "RouteEstimateV2"),
    ("backend.app.domain.trip_models", "ScheduleItemV2"),
    ("backend.app.domain.trip_models", "TripPlanV2"),
    ("backend.app.domain.trip_models", "TripRequestV2"),
    ("backend.app.domain.trip_models", "WeatherInfoV2"),
    ("backend.app.domain.validation_models", "ValidationIssueV2"),
    ("backend.app.domain.validation_models", "ValidationReportV2"),
]


def checkpoint_database_url(url: str | None = None) -> str:
    """Convert SQLAlchemy's Psycopg URL to the DSN accepted by Psycopg."""
    configured = url or database_url()
    if configured.startswith("postgresql+psycopg://"):
        return configured.replace("postgresql+psycopg://", "postgresql://", 1)
    if configured.startswith(("postgresql://", "postgres://")):
        return configured
    raise ValueError("JourneyGraph checkpoints require a PostgreSQL DATABASE_URL.")


def checkpoint_serializer() -> JsonPlusSerializer:
    """Allow only project-owned Pydantic types during checkpoint restoration."""
    return JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_CHECKPOINT_TYPES)


@contextmanager
def open_postgres_checkpointer(
    url: str | None = None,
    *,
    setup: bool = False,
) -> Generator[PostgresSaver, None, None]:
    """Open one correctly configured saver and close its connection afterwards."""
    with psycopg.connect(
        checkpoint_database_url(url),
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        saver = PostgresSaver(connection, serde=checkpoint_serializer())
        if setup:
            saver.setup()
        yield saver
