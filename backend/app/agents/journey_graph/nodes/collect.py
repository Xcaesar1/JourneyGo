"""Phase 3 collection boundary returning only structured objects."""

from __future__ import annotations

from typing import Any

from ....services.attraction_discovery import (
    AttractionDiscoveryProvider,
    NoopAttractionDiscoveryProvider,
)
from ..state import TripState


def make_collect_node(
    provider: AttractionDiscoveryProvider | None = None,
):
    configured_provider = provider or NoopAttractionDiscoveryProvider()
    enforce_candidate_policy = not isinstance(configured_provider, NoopAttractionDiscoveryProvider)

    def collect_with_provider(state: TripState) -> dict[str, Any]:
        request = state["request"]
        poi_candidates: dict[str, list[dict[str, Any]]] = {}
        discovery_issues: dict[str, list[str]] = {}
        for destination in request.destinations:
            page = configured_provider.discover(
                destination.city,
                interests=request.interests,
                must_visit=request.must_visit,
                avoid=request.avoid,
                days=destination.days,
                limit=40,
            )
            poi_candidates[destination.city] = [item.model_dump(mode="json") for item in page.items]
            if page.issues:
                discovery_issues[destination.city] = page.issues
        return {
            "sources": list(state.get("sources", [])),
            "poi_candidates": poi_candidates,
            "weather": {destination.city: [] for destination in request.destinations},
            "transport_options": list(state.get("transport_options", [])),
            "metrics": {
                **state.get("metrics", {}),
                "collected": True,
                "poi_candidate_count": sum(map(len, poi_candidates.values())),
                "poi_discovery_issues": discovery_issues,
                "poi_candidate_policy_enforced": enforce_candidate_policy,
            },
        }

    return collect_with_provider


collect = make_collect_node()
