"""Unit tests for the typed Phase 3 JourneyGraph skeleton."""

from __future__ import annotations

import pytest
from backend.app.agents.journey_graph import build_journey_graph
from backend.app.agents.journey_graph.nodes import (
    build_placeholder_plan,
    collect,
    enrich_plan,
    make_draft_node,
    make_plan_intercity_transport_node,
    normalize_request,
    persist,
    prepare_research_queries,
    validate_stub,
)
from backend.app.domain.trip_models import (
    TRIP_REQUEST_V2_EXAMPLE,
    AttractionV2,
    TripPlanV2,
    TripRequestV2,
)
from backend.app.services.routing import NoopRouteEstimateProvider
from pydantic import ValidationError


def _initial_state() -> dict:
    return {
        "trip_id": "trip_graph_test",
        "task_id": "task_graph_test",
        "request": TRIP_REQUEST_V2_EXAMPLE,
    }


def _normalized_state() -> dict:
    initial = _initial_state()
    return {**initial, **normalize_request(initial)}


def _enriched_state() -> dict:
    state = _normalized_state()
    state.update(make_plan_intercity_transport_node(NoopRouteEstimateProvider())(state))
    state.update(make_draft_node(build_placeholder_plan)(state))
    state.update(enrich_plan(state))
    return state


def test_normalize_request_node_returns_typed_request() -> None:
    result = normalize_request(_initial_state())

    assert isinstance(result["request"], TripRequestV2)
    assert result["metrics"] == {"normalized": True}


def test_collect_node_returns_structured_provider_boundaries() -> None:
    result = collect(_normalized_state())

    assert result["sources"] == []
    assert result["poi_candidates"] == {"Tokyo": [], "Kyoto": []}
    assert result["weather"] == {"Tokyo": [], "Kyoto": []}
    assert result["metrics"]["collected"] is True


def test_prepare_research_node_returns_five_queries_per_city() -> None:
    result = prepare_research_queries(_normalized_state())

    assert len(result["research_queries"]) == 10
    assert result["metrics"]["research_prepared"] is True


def test_draft_node_returns_typed_plan() -> None:
    state = _normalized_state()
    state.update(make_plan_intercity_transport_node(NoopRouteEstimateProvider())(state))
    result = make_draft_node(build_placeholder_plan)(state)

    assert isinstance(result["draft_plan"], TripPlanV2)
    assert result["draft_plan"].transport_options
    assert result["draft_plan"].route_matrix
    assert result["metrics"]["drafted"] is True


def test_draft_node_preserves_request_identity_over_model_output() -> None:
    state = _normalized_state()
    state.update(make_plan_intercity_transport_node(NoopRouteEstimateProvider())(state))

    def untrusted_generator(_: dict) -> TripPlanV2:
        return build_placeholder_plan(state).model_copy(
            update={
                "origin": r"\u0053\u0068\u0061\u006e\u0067\u0068\u0061\u0069",
                "city": "Wrong city",
                "cities": ["Wrong city"],
            }
        )

    plan = make_draft_node(untrusted_generator)(state)["draft_plan"]

    assert plan.origin == "Shanghai"
    assert plan.city == "Tokyo"
    assert plan.cities == ["Tokyo", "Kyoto"]
    assert plan.start_date == state["request"].start_date
    assert plan.end_date == state["request"].end_date


def test_draft_node_restores_selected_candidate_with_coordinates_when_model_omits_it() -> None:
    state = _normalized_state()
    state.update(make_plan_intercity_transport_node(NoopRouteEstimateProvider())(state))
    state["metrics"] = {**state["metrics"], "poi_candidate_policy_enforced": True}
    state["poi_candidates"] = {
        "Tokyo": [
            {
                "poi_id": "tokyo-sensoji",
                "name": "Senso-ji",
                "city": "Tokyo",
                "address": "Asakusa",
                "longitude": 139.7967,
                "latitude": 35.7148,
                "category": "attraction",
                "rating": 4.8,
                "image": {"url": "https://example.test/sensoji.jpg", "source": "amap"},
                "recommendation_score": 95,
                "recommendation_reason": "User-selected verified POI",
                "matched_interests": [],
                "is_must_visit": True,
            }
        ],
        "Kyoto": [],
    }

    def generator_with_city_alias(_: dict) -> TripPlanV2:
        plan = build_placeholder_plan(state)
        first_day = plan.days[0].model_copy(update={"city": "Tokyo Metropolis"})
        return plan.model_copy(update={"days": [first_day, *plan.days[1:]]})

    plan = make_draft_node(generator_with_city_alias)(state)["draft_plan"]
    attraction = plan.days[0].attractions[0]

    assert plan.days[0].city == "Tokyo"
    assert attraction.name == "Senso-ji"
    assert attraction.poi_id == "tokyo-sensoji"
    assert attraction.location is not None
    assert attraction.location.longitude == 139.7967
    assert attraction.image_source == "amap"


def test_draft_node_caps_one_day_candidates_and_keeps_must_visit_first() -> None:
    state = _normalized_state()
    state.update(make_plan_intercity_transport_node(NoopRouteEstimateProvider())(state))
    state["metrics"] = {**state["metrics"], "poi_candidate_policy_enforced": True}
    candidates = [
        {
            "poi_id": f"tokyo-{index}",
            "name": "Senso-ji" if index == 0 else f"Tokyo attraction {index}",
            "city": "Tokyo",
            "address": "Tokyo",
            "longitude": 139.7 + index / 100,
            "latitude": 35.6 + index / 100,
            "category": "attraction",
            "rating": 4.5,
            "image": {"url": "", "source": "placeholder"},
            "recommendation_score": 90 - index,
            "recommendation_reason": "Verified POI",
            "matched_interests": [],
            "is_must_visit": index == 0,
        }
        for index in range(8)
    ]
    state["poi_candidates"] = {"Tokyo": candidates, "Kyoto": []}

    def crowded_generator(_: dict) -> TripPlanV2:
        plan = build_placeholder_plan(state)
        first_day = plan.days[0].model_copy(
            update={
                "attractions": [AttractionV2(name=candidate["name"]) for candidate in candidates]
            }
        )
        return plan.model_copy(update={"days": [first_day, *plan.days[1:]]})

    plan = make_draft_node(crowded_generator)(state)["draft_plan"]

    assert len(plan.days[0].attractions) == 5
    assert plan.days[0].attractions[0].name == "Senso-ji"
    assert all(attraction.location is not None for attraction in plan.days[0].attractions)


def test_validate_stub_node_returns_typed_report() -> None:
    state = _enriched_state()

    result = validate_stub(state)

    assert result["validation_report"].has_critical is False
    assert result["metrics"]["validated"] is True


def test_persist_node_finalizes_valid_typed_plan() -> None:
    state = _enriched_state()
    state.update(validate_stub(state))

    result = persist(state)

    assert result["final_plan"] is state["draft_plan"]
    assert result["metrics"]["persisted"] is True


def test_journey_graph_nodes_are_independently_executable() -> None:
    state = {**_initial_state(), **normalize_request(_initial_state())}
    state.update(collect(state))
    state.update(make_plan_intercity_transport_node(NoopRouteEstimateProvider())(state))
    state.update(make_draft_node(build_placeholder_plan)(state))
    state.update(enrich_plan(state))
    state.update(validate_stub(state))
    state.update(persist(state))

    assert isinstance(state["request"], TripRequestV2)
    assert isinstance(state["final_plan"], TripPlanV2)
    assert state["final_plan"].cities == ["Tokyo", "Kyoto"]
    assert state["validation_report"].has_critical is False


def test_compiled_journey_graph_runs_all_phase_three_nodes() -> None:
    result = build_journey_graph().invoke(_initial_state())

    assert isinstance(result["final_plan"], TripPlanV2)
    assert result["metrics"]["normalized"] is True
    assert result["metrics"]["research_prepared"] is True
    assert result["metrics"]["researched"] is True
    assert result["metrics"]["research_unknown_count"] == 8
    assert result["metrics"]["collected"] is True
    assert result["metrics"]["transport_planned"] is True
    assert result["metrics"]["transport_leg_count"] == 2
    assert result["metrics"]["drafted"] is True
    assert result["metrics"]["timeline_enriched"] is True
    assert result["metrics"]["budget_recalculated"] is True
    assert result["metrics"]["validated"] is True
    assert result["metrics"]["persisted"] is True


def test_journey_graph_reports_real_node_execution_order() -> None:
    observed: list[str] = []

    build_journey_graph(node_observer=observed.append).invoke(_initial_state())

    assert observed[:5] == [
        "normalize_request",
        "prepare_research_queries",
        "research_web",
        "collect",
        "plan_intercity_transport",
    ]
    assert "draft" in observed
    assert "deterministic_validate" in observed
    assert observed[-1] == "persist"


def test_journey_graph_mermaid_contains_ordered_nodes() -> None:
    mermaid = build_journey_graph().get_graph().draw_mermaid()

    expected_nodes = [
        "normalize_request",
        "prepare_research_queries",
        "research_web",
        "collect",
        "plan_intercity_transport",
        "draft",
        "enrich_plan",
        "deterministic_validate",
        "revise_plan",
        "persist",
    ]
    assert all(node in mermaid for node in expected_nodes)
    assert mermaid.index("normalize_request") < mermaid.index("persist")


def test_trip_plan_v2_rejects_non_contiguous_days() -> None:
    normalized = {**_initial_state(), **normalize_request(_initial_state())}
    payload = build_placeholder_plan(normalized).model_dump(mode="json")
    payload["days"][1]["day_index"] = 9

    with pytest.raises(ValidationError, match="day_index values must be contiguous"):
        TripPlanV2.model_validate(payload)
