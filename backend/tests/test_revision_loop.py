"""Bounded validate/revise loop behavior."""

from __future__ import annotations

from backend.app.agents.journey_graph import build_journey_graph
from backend.app.agents.journey_graph.nodes import build_placeholder_plan
from backend.app.domain.trip_models import AttractionV2, TripPlanV2


def _request() -> dict:
    return {
        "origin": "Shanghai",
        "destinations": [{"city": "Tokyo", "days": 1}],
        "start_date": "2026-10-10",
        "end_date": "2026-10-10",
        "travel_days": 1,
        "travelers": 1,
        "pace": "balanced",
        "daily_start_time": "09:00:00",
        "daily_end_time": "21:00:00",
        "language": "en",
    }


def _invoke(generator) -> dict:
    return build_journey_graph(draft_generator=generator).invoke(
        {
            "trip_id": "trip-revision",
            "task_id": "task-revision",
            "request": _request(),
        }
    )


def test_closed_attraction_is_removed_in_one_revision() -> None:
    def generator(state) -> TripPlanV2:
        plan = build_placeholder_plan(state)
        attraction = AttractionV2(
            name="Closed museum",
            visit_duration=60,
            closed_dates=[state["request"].start_date],
        )
        day = plan.days[0].model_copy(update={"attractions": [attraction]})
        return plan.model_copy(update={"days": [day]})

    result = _invoke(generator)

    assert result["final_plan"].revision_count == 1
    assert result["final_plan"].validation_report.has_critical is False
    assert result["final_plan"].days[0].attractions == []
    assert result["metrics"]["unresolved_critical_count"] == 0


def test_revision_loop_stops_after_two_rounds_and_preserves_issues() -> None:
    def generator(state) -> TripPlanV2:
        plan = build_placeholder_plan(state)
        attractions = [
            AttractionV2(name=f"Attraction {index}", visit_duration=30)
            for index in range(8)
        ]
        day = plan.days[0].model_copy(update={"attractions": attractions})
        return plan.model_copy(update={"days": [day]})

    result = _invoke(generator)
    final_plan = result["final_plan"]

    assert final_plan.revision_count == 2
    assert len(final_plan.days[0].attractions) == 6
    assert final_plan.validation_report.has_critical is True
    assert any(
        issue.code == "daily_intensity_excessive"
        for issue in final_plan.validation_report.issues
    )
    assert result["metrics"]["unresolved_critical_count"] > 0
