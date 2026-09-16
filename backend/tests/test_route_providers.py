"""Route provider and deterministic intercity transport tests."""

from __future__ import annotations

import logging

import httpx
from backend.app.agents.journey_graph.nodes import make_plan_intercity_transport_node
from backend.app.agents.journey_graph.nodes.normalize import normalize_request
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE
from backend.app.services.routing import (
    AmapRouteEstimateProvider,
    NoopRouteEstimateProvider,
    RouteEstimateProvider,
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_amap_route_provider_returns_distance_and_rounded_duration() -> None:
    geocodes = {
        "Shanghai": "121.4737,31.2304",
        "Tokyo": "139.6917,35.6895",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/geocode/geo"):
            address = request.url.params["address"]
            return httpx.Response(
                200,
                json={"status": "1", "geocodes": [{"location": geocodes[address]}]},
            )
        assert request.url.params["type"] == "1"
        return httpx.Response(
            200,
            json={"status": "1", "results": [{"distance": "1100500", "duration": "3599"}]},
        )

    client = _client(handler)
    provider = AmapRouteEstimateProvider("test-key", client=client)
    result = provider.estimate("Shanghai", "Tokyo")
    client.close()

    assert isinstance(provider, RouteEstimateProvider)
    assert result.status == "verified"
    assert result.distance_meters == 1_100_500
    assert result.duration_minutes == 60
    assert result.provider == "amap"


def test_amap_route_provider_degrades_without_exposing_provider_payload() -> None:
    client = _client(
        lambda _request: httpx.Response(
            200,
            json={"status": "0", "info": "INVALID_USER_KEY test-key"},
        )
    )
    result = AmapRouteEstimateProvider("test-key", client=client).estimate("A", "B")
    client.close()

    assert result.status == "unavailable"
    assert "test-key" not in result.detail
    assert "INVALID_USER_KEY" not in result.detail


def test_amap_route_provider_suppresses_query_credentials_in_http_logs(caplog) -> None:
    secret = "test-query-secret-123456"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/geocode/geo"):
            return httpx.Response(
                200,
                json={"status": "1", "geocodes": [{"location": "120.0,30.0"}]},
            )
        return httpx.Response(
            200,
            json={"status": "1", "results": [{"distance": "1000", "duration": "600"}]},
        )

    caplog.set_level(logging.INFO, logger="httpx")
    client = _client(handler)
    result = AmapRouteEstimateProvider(secret, client=client).estimate("A", "B")
    client.close()

    assert result.status == "verified"
    assert secret not in caplog.text


def test_intercity_node_builds_origin_and_between_destination_legs() -> None:
    state = {
        "trip_id": "trip-transport",
        "task_id": "task-transport",
        "request": TRIP_REQUEST_V2_EXAMPLE,
    }
    state.update(normalize_request(state))

    result = make_plan_intercity_transport_node(NoopRouteEstimateProvider())(state)

    assert [(item.origin, item.destination) for item in result["route_estimates"]] == [
        ("Shanghai", "Tokyo"),
        ("Tokyo", "Kyoto"),
    ]
    assert len(result["transport_options"]) == 4
    assert [item.recommended for item in result["transport_options"]].count(True) == 2
    assert all(item.caveats for item in result["transport_options"])
    assert all("availability" in item.caveats[0] for item in result["transport_options"])
    assert result["metrics"]["route_unavailable_count"] == 2
