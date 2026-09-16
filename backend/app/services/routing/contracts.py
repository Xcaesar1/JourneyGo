"""Provider-neutral route estimation contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.trip_models import RouteEstimateV2


@runtime_checkable
class RouteEstimateProvider(Protocol):
    """Estimate distance and duration without returning live ticket claims."""

    name: str

    def estimate(self, origin: str, destination: str) -> RouteEstimateV2: ...
