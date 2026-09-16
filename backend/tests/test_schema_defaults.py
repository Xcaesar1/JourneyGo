"""Regression coverage for isolated legacy Pydantic list defaults."""

from __future__ import annotations

import pytest
from backend.app.models.schemas import (
    CityStay,
    DayPlan,
    KnowledgeGraphData,
    POISearchResponse,
    TripChatRequest,
    TripPlan,
    TripRequest,
    WeatherResponse,
)

LIST_DEFAULT_FIELDS = (
    (TripRequest, ("cities", "preferences")),
    (DayPlan, ("attractions", "meals")),
    (TripPlan, ("cities", "weather_info")),
    (KnowledgeGraphData, ("nodes", "edges", "categories")),
    (POISearchResponse, ("data",)),
    (WeatherResponse, ("data",)),
    (TripChatRequest, ("history",)),
)


@pytest.mark.parametrize(("model", "field_names"), LIST_DEFAULT_FIELDS)
def test_legacy_list_fields_use_default_factory(model, field_names) -> None:
    for field_name in field_names:
        assert model.model_fields[field_name].default_factory is list


def _assert_lists_are_isolated(first, second, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        first_list = getattr(first, field_name)
        second_list = getattr(second, field_name)
        second_snapshot = list(second_list)

        assert first_list is not second_list
        first_list.append(object())
        assert second_list == second_snapshot


def test_legacy_list_defaults_are_isolated_between_instances() -> None:
    request_a = TripRequest(
        cities=[CityStay(city="Osaka", days=3)],
        start_date="2026-10-10",
        end_date="2026-10-12",
        travel_days=3,
        transportation="train",
        accommodation="hotel",
    )
    request_b = TripRequest(
        cities=[CityStay(city="Osaka", days=3)],
        start_date="2026-10-10",
        end_date="2026-10-12",
        travel_days=3,
        transportation="train",
        accommodation="hotel",
    )
    _assert_lists_are_isolated(request_a, request_b, ("cities", "preferences"))

    day_a = DayPlan(
        date="2026-10-10",
        day_index=0,
        description="Arrival day",
        transportation="train",
        accommodation="hotel",
    )
    day_b = DayPlan(
        date="2026-10-10",
        day_index=0,
        description="Arrival day",
        transportation="train",
        accommodation="hotel",
    )
    _assert_lists_are_isolated(day_a, day_b, ("attractions", "meals"))

    plan_a = TripPlan(
        city="Osaka",
        start_date="2026-10-10",
        end_date="2026-10-12",
        days=[],
        overall_suggestions="Keep it simple.",
    )
    plan_b = TripPlan(
        city="Osaka",
        start_date="2026-10-10",
        end_date="2026-10-12",
        days=[],
        overall_suggestions="Keep it simple.",
    )
    _assert_lists_are_isolated(plan_a, plan_b, ("cities", "weather_info"))

    _assert_lists_are_isolated(
        KnowledgeGraphData(),
        KnowledgeGraphData(),
        ("nodes", "edges", "categories"),
    )
    _assert_lists_are_isolated(
        POISearchResponse(success=True, message="ok"),
        POISearchResponse(success=True, message="ok"),
        ("data",),
    )
    _assert_lists_are_isolated(
        WeatherResponse(success=True, message="ok"),
        WeatherResponse(success=True, message="ok"),
        ("data",),
    )
    _assert_lists_are_isolated(
        TripChatRequest(message="hello", trip_plan={}),
        TripChatRequest(message="hello", trip_plan={}),
        ("history",),
    )
