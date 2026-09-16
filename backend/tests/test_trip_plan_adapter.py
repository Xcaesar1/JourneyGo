"""Compatibility checks for JourneyGraph output consumed by the current frontend."""

from __future__ import annotations

from backend.app.adapters import trip_plan_v2_to_legacy
from backend.app.agents.journey_graph.nodes import build_placeholder_plan, normalize_request
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE, TripPlanV2
from backend.app.models.schemas import TripPlan
from backend.app.services.knowledge_graph_service import build_knowledge_graph


def _placeholder_v2_plan() -> TripPlanV2:
    state = {
        "trip_id": "trip_adapter_test",
        "task_id": "task_adapter_test",
        "request": TRIP_REQUEST_V2_EXAMPLE,
    }
    state.update(normalize_request(state))
    return build_placeholder_plan(state)


def test_trip_plan_v2_adapter_matches_current_frontend_contract() -> None:
    adapted = trip_plan_v2_to_legacy(_placeholder_v2_plan())
    payload = adapted.model_dump(mode="json")

    assert isinstance(adapted, TripPlan)
    assert set(payload) == {
        "origin",
        "city",
        "cities",
        "start_date",
        "end_date",
        "days",
        "transport_options",
        "route_matrix",
        "weather_info",
        "overall_suggestions",
        "budget",
        "source_evidence",
        "research_updated_at",
        "research_status",
        "validation_report",
        "revision_count",
    }
    assert payload["origin"] == "Shanghai"
    assert "schema_version" not in payload
    assert payload["days"][0]["date"] == "2026-10-10"
    assert payload["days"][-1]["day_index"] == 4


def test_adapter_maps_nested_items_and_omits_unmappable_attractions() -> None:
    payload = _placeholder_v2_plan().model_dump(mode="json")
    payload["days"][0]["attractions"] = [
        {
            "name": "Mapped museum",
            "address": "1 Museum Road",
            "location": {"longitude": 139.7, "latitude": 35.6},
            "visit_duration": 90,
            "description": "Mapped from typed output.",
            "category": "museum",
            "ticket_price": 50,
            "reservation_required": True,
            "reservation_tips": "Reserve ahead.",
        },
        {
            "name": "No-coordinate suggestion",
            "address": "",
            "location": None,
            "visit_duration": 60,
            "description": "Must not be placed at false coordinates.",
            "category": "attraction",
            "ticket_price": 0,
            "reservation_required": False,
            "reservation_tips": "",
        },
    ]
    payload["days"][0]["meals"] = [
        {
            "type": "lunch",
            "name": "Typed lunch",
            "address": None,
            "location": None,
            "description": "Local meal",
            "estimated_cost": 80,
        }
    ]
    payload["weather_info"] = [
        {
            "date": "2026-10-10",
            "city": "Tokyo",
            "day_weather": "clear",
            "night_weather": "cloudy",
            "day_temp": 22,
            "night_temp": 16,
            "wind_direction": "east",
            "wind_power": "2",
        }
    ]

    adapted = trip_plan_v2_to_legacy(TripPlanV2.model_validate(payload))

    assert [item.name for item in adapted.days[0].attractions] == ["Mapped museum"]
    assert adapted.days[0].attractions[0].location.longitude == 139.7
    assert adapted.days[0].meals[0].estimated_cost == 80
    assert adapted.weather_info[0].day_temp == 22


def test_adapted_plan_builds_the_existing_frontend_graph_payload() -> None:
    adapted = trip_plan_v2_to_legacy(_placeholder_v2_plan())

    graph = build_knowledge_graph(adapted, language="en")

    assert isinstance(graph, dict)
    assert graph["categories"]
