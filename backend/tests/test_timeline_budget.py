"""Deterministic timeline and budget calculation tests."""

from __future__ import annotations

from backend.app.agents.journey_graph.nodes import (
    build_placeholder_plan,
    enrich_plan,
    make_plan_intercity_transport_node,
    normalize_request,
)
from backend.app.domain.trip_models import (
    TRIP_REQUEST_V2_EXAMPLE,
    AttractionV2,
    BudgetV2,
    HotelV2,
    LocationV2,
    MealV2,
)
from backend.app.services.routing import NoopRouteEstimateProvider


def _state_with_activities() -> dict:
    state = {
        "trip_id": "trip-timeline",
        "task_id": "task-timeline",
        "request": TRIP_REQUEST_V2_EXAMPLE,
    }
    state.update(normalize_request(state))
    state.update(make_plan_intercity_transport_node(NoopRouteEstimateProvider())(state))
    plan = build_placeholder_plan(state)
    first_day = plan.days[0].model_copy(
        update={
            "hotel": HotelV2(name="Test hotel", estimated_cost=300),
            "attractions": [
                AttractionV2(
                    name="Museum A",
                    location=LocationV2(longitude=139.70, latitude=35.68),
                    visit_duration=90,
                    ticket_price=100,
                ),
                AttractionV2(
                    name="Garden B",
                    location=LocationV2(longitude=139.72, latitude=35.69),
                    visit_duration=60,
                    ticket_price=50,
                ),
            ],
            "meals": [
                MealV2(
                    type="lunch",
                    name="Lunch",
                    location=LocationV2(longitude=139.71, latitude=35.685),
                    estimated_cost=50,
                )
            ],
        }
    )
    state["draft_plan"] = plan.model_copy(
        update={
            "days": [first_day, *plan.days[1:]],
            "budget": BudgetV2(total=999_999),
        }
    )
    return state


def test_enrichment_builds_contiguous_closed_daily_timeline() -> None:
    result = enrich_plan(_state_with_activities())
    plan = result["draft_plan"]
    timeline = plan.days[0].timeline

    assert timeline[0].start.strftime("%H:%M") == "09:00"
    assert timeline[-1].end.strftime("%H:%M") == "21:00"
    assert all(left.end == right.start for left, right in zip(timeline, timeline[1:]))
    assert len({item.item_id for item in timeline}) == len(timeline)
    assert all(
        item.duration_minutes == round((item.end - item.start).total_seconds() / 60)
        for item in timeline
    )
    assert plan.days[0].arrangement_rationale
    assert result["metrics"]["timeline_enriched"] is True


def test_enrichment_adds_daily_route_matrix_estimates() -> None:
    plan = enrich_plan(_state_with_activities())["draft_plan"]
    local_routes = [item for item in plan.route_matrix if item.provider == "local-estimate"]

    assert len(plan.route_matrix) == 4
    assert len(local_routes) == 2
    assert all(item.status == "estimated" and item.distance_meters for item in local_routes)


def test_budget_is_recalculated_from_plan_items_and_is_internally_consistent() -> None:
    plan = enrich_plan(_state_with_activities())["draft_plan"]
    budget = plan.budget

    assert budget is not None
    assert budget.total_attractions == 300
    assert budget.total_hotels == 300
    assert budget.total_meals == 100
    assert budget.total_transportation > 0
    assert budget.total_inter_city_transport == 0
    assert budget.total == (
        budget.total_attractions
        + budget.total_hotels
        + budget.total_meals
        + budget.total_transportation
        + budget.total_inter_city_transport
    )
    assert budget.total != 999_999
