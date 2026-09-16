"""Request normalization without model calls."""

from __future__ import annotations

from typing import Any

from ....domain.trip_models import TripRequestV2
from ..state import TripState


def normalize_request(state: TripState) -> dict[str, Any]:
    request = TripRequestV2.model_validate(state["request"])
    return {
        "request": request,
        "revision_count": state.get("revision_count", 0),
        "errors": list(state.get("errors", [])),
        "metrics": {**state.get("metrics", {}), "normalized": True},
    }
