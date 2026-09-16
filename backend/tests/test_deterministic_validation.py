"""Rule coverage for the Phase 5 deterministic validator."""

from __future__ import annotations

from datetime import time

from backend.app.agents.journey_graph.nodes import (
    build_placeholder_plan,
    enrich_plan,
    make_plan_intercity_transport_node,
    normalize_request,
    revise_plan,
    validate_plan,
)
from backend.app.domain.trip_models import (
    TRIP_REQUEST_V2_EXAMPLE,
    AttractionV2,
    BudgetV2,
    LocationV2,
)
from backend.app.domain.validation_models import ValidationIssueV2, ValidationReportV2
from backend.app.services.routing import NoopRouteEstimateProvider


def _state() -> dict:
    state = {
        "trip_id": "trip-validation",
        "task_id": "task-validation",
        "request": TRIP_REQUEST_V2_EXAMPLE,
    }
    state.update(normalize_request(state))
    state.update(make_plan_intercity_transport_node(NoopRouteEstimateProvider())(state))
    state["draft_plan"] = build_placeholder_plan(state)
    state.update(enrich_plan(state))
    return state


def _codes(state: dict) -> set[str]:
    return {issue.code for issue in validate_plan(state)["validation_report"].issues}


def test_valid_enriched_plan_has_no_critical_and_attaches_report() -> None:
    state = _state()
    result = validate_plan(state)

    assert result["validation_report"].has_critical is False
    assert result["draft_plan"].validation_report == result["validation_report"]
    assert result["metrics"]["validation_warning_count"] == 2


def test_structure_validator_detects_wrong_city_and_duplicate_item_ids() -> None:
    state = _state()
    plan = state["draft_plan"]
    first = plan.days[0]
    second = plan.days[1]
    duplicated = second.timeline[0].model_copy(update={"item_id": first.timeline[0].item_id})
    state["draft_plan"] = plan.model_copy(
        update={
            "days": [
                first.model_copy(update={"city": "Wrong City"}),
                second.model_copy(update={"timeline": [duplicated, *second.timeline[1:]]}),
                *plan.days[2:],
            ]
        }
    )

    assert {"day_city_mismatch", "duplicate_item_id"} <= _codes(state)


def test_time_validator_detects_overrun_and_inconsistent_duration() -> None:
    state = _state()
    plan = state["draft_plan"]
    day = plan.days[0]
    last = day.timeline[-1]
    broken = last.model_copy(
        update={
            "end": last.end.replace(hour=23),
            "duration_minutes": 1,
        }
    )
    state["draft_plan"] = plan.model_copy(
        update={"days": [day.model_copy(update={"timeline": [*day.timeline[:-1], broken]}), *plan.days[1:]]}
    )

    assert {"invalid_item_duration", "daily_window_exceeded"} <= _codes(state)


def test_route_validator_detects_obviously_impossible_local_route() -> None:
    state = _state()
    plan = state["draft_plan"]
    impossible_route = plan.route_matrix[0].model_copy(
        update={
            "provider": "local-estimate",
            "status": "estimated",
            "distance_meters": 900_000,
            "duration_minutes": 30,
        }
    )
    first_item = plan.days[0].timeline[0].model_copy(
        update={"route_estimate_id": impossible_route.estimate_id, "duration_minutes": 30}
    )
    first_day = plan.days[0].model_copy(
        update={"timeline": [first_item, *plan.days[0].timeline[1:]]}
    )
    state["draft_plan"] = plan.model_copy(
        update={"route_matrix": [impossible_route, *plan.route_matrix[1:]], "days": [first_day, *plan.days[1:]]}
    )

    assert "impossible_local_route" in _codes(state)


def test_intercity_route_uses_selected_transport_duration_not_driving_duration() -> None:
    state = _state()
    plan = state["draft_plan"]
    item = plan.days[0].timeline[0]
    state["transport_options"] = [
        option.model_copy(update={"estimated_duration_minutes": item.duration_minutes})
        if option.recommended and option.route_estimate_id == item.route_estimate_id
        else option
        for option in state["transport_options"]
    ]
    route = plan.route_matrix[0].model_copy(
        update={
            "status": "verified",
            "duration_minutes": item.duration_minutes + 300,
        }
    )
    state["draft_plan"] = plan.model_copy(
        update={"route_matrix": [route, *plan.route_matrix[1:]]}
    )

    assert "route_duration_underallocated" not in _codes(state)


def test_intercity_route_detects_time_below_selected_transport_duration() -> None:
    state = _state()
    plan = state["draft_plan"]
    day = plan.days[0]
    item = day.timeline[0]
    state["transport_options"] = [
        option.model_copy(update={"estimated_duration_minutes": item.duration_minutes})
        if option.recommended and option.route_estimate_id == item.route_estimate_id
        else option
        for option in state["transport_options"]
    ]
    shortened = item.model_copy(update={"duration_minutes": item.duration_minutes - 1})
    state["draft_plan"] = plan.model_copy(
        update={
            "days": [
                day.model_copy(update={"timeline": [shortened, *day.timeline[1:]]}),
                *plan.days[1:],
            ]
        }
    )

    assert "route_duration_underallocated" in _codes(state)


def test_budget_validator_detects_arithmetic_and_requested_budget_conflicts() -> None:
    state = _state()
    request_payload = {**TRIP_REQUEST_V2_EXAMPLE, "budget_total": "10"}
    state["request"] = normalize_request({"request": request_payload})["request"]
    state["draft_plan"] = state["draft_plan"].model_copy(
        update={
            "budget": BudgetV2(
                total_attractions=100,
                total_hotels=100,
                total_meals=100,
                total_transportation=100,
                total_inter_city_transport=100,
                total=999,
            )
        }
    )

    assert {"budget_total_mismatch", "budget_exceeded"} <= _codes(state)


def test_opening_hours_validator_detects_closure_and_hours_conflicts() -> None:
    state = _state()
    plan = state["draft_plan"]
    day = plan.days[0]
    attraction = AttractionV2(
        name="Closed museum",
        location=LocationV2(longitude=139.7, latitude=35.6),
        visit_duration=60,
        opening_time=time(12, 0),
        closing_time=time(11, 30),
        closed_dates=[day.date],
        source_evidence_ids=["official-hours"],
    )
    state["draft_plan"] = plan.model_copy(
        update={"days": [day.model_copy(update={"attractions": [attraction]}), *plan.days[1:]]}
    )
    state.update(enrich_plan(state))

    assert {"attraction_closed", "before_opening_time", "after_closing_time"} <= _codes(state)


def test_intensity_validator_detects_overloaded_balanced_day() -> None:
    state = _state()
    plan = state["draft_plan"]
    day = plan.days[1]
    attractions = [
        AttractionV2(name=f"Attraction {index}", visit_duration=30)
        for index in range(6)
    ]
    state["draft_plan"] = plan.model_copy(
        update={"days": [plan.days[0], day.model_copy(update={"attractions": attractions}), *plan.days[2:]]}
    )
    state.update(enrich_plan(state))

    assert "daily_intensity_excessive" in _codes(state)


def test_revision_never_removes_must_visit_when_trimming_an_overloaded_day() -> None:
    state = _state()
    plan = state["draft_plan"]
    day = plan.days[0].model_copy(
        update={
            "attractions": [
                AttractionV2(name="Senso-ji"),
                AttractionV2(name="Optional stop"),
            ]
        }
    )
    report = ValidationReportV2(
        issues=[
            ValidationIssueV2(
                code="daily_window_exceeded",
                severity="critical",
                day_index=0,
                message="The day is overloaded.",
            )
        ]
    )
    state["draft_plan"] = plan.model_copy(update={"days": [day, *plan.days[1:]]})
    state["validation_report"] = report

    revised = revise_plan(state)["draft_plan"]

    assert [item.name for item in revised.days[0].attractions] == ["Senso-ji"]
