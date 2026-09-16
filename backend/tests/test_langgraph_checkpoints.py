"""Unit checks for safe JourneyGraph checkpoint configuration."""

from __future__ import annotations

import pytest
from backend.app.agents.journey_graph.checkpoint import (
    checkpoint_database_url,
    checkpoint_serializer,
)
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE, TripRequestV2


def test_checkpoint_database_url_converts_sqlalchemy_driver() -> None:
    assert checkpoint_database_url(
        "postgresql+psycopg://user:password@postgres:5432/journeyops"
    ) == "postgresql://user:password@postgres:5432/journeyops"
    assert checkpoint_database_url(
        "postgresql://user:password@postgres:5432/journeyops"
    ) == "postgresql://user:password@postgres:5432/journeyops"


def test_checkpoint_database_url_rejects_non_postgres_backends() -> None:
    with pytest.raises(ValueError, match="require a PostgreSQL"):
        checkpoint_database_url("sqlite:///journeyops.db")


def test_checkpoint_serializer_round_trips_allowlisted_models() -> None:
    serializer = checkpoint_serializer()
    request = TripRequestV2.model_validate(TRIP_REQUEST_V2_EXAMPLE)

    restored = serializer.loads_typed(serializer.dumps_typed(request))

    assert restored == request
    assert isinstance(restored, TripRequestV2)
