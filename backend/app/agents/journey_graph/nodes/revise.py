"""Targeted deterministic revisions driven by validation issues."""

from __future__ import annotations

from typing import Any

from ....domain.trip_models import DayPlanV2, TripPlanV2
from ..state import TripState

_REMOVE_ITEM_CODES = {
    "attraction_closed",
    "before_opening_time",
    "after_closing_time",
}
_TRIM_DAY_CODES = {
    "daily_window_exceeded",
    "daily_commute_excessive",
    "daily_intensity_excessive",
    "transfer_day_overloaded",
    "walking_limit_exceeded",
}


def _place_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _is_must_visit(name: str, must_visit: list[str]) -> bool:
    key = _place_key(name)
    return any(term and (term in key or key in term) for term in must_visit)


def _next_attraction_name(day: DayPlanV2, transport_item_id: str) -> str | None:
    for index, item in enumerate(day.timeline):
        if item.item_id != transport_item_id:
            continue
        for candidate in day.timeline[index + 1 :]:
            if candidate.item_type == "attraction":
                return candidate.reference_name
        break
    return None


def _revise_days(state: TripState, plan: TripPlanV2) -> list[DayPlanV2]:
    report = state["validation_report"]
    issues_by_day: dict[int, list[Any]] = {}
    for issue in report.issues:
        if issue.day_index is not None:
            issues_by_day.setdefault(issue.day_index, []).append(issue)

    expected_cities = [
        destination.city
        for destination in state["request"].destinations
        for _ in range(destination.days)
    ]
    must_visit = [_place_key(value) for value in state["request"].must_visit]
    revised_days: list[DayPlanV2] = []
    for day in plan.days:
        issues = issues_by_day.get(day.day_index, [])
        timeline_by_id = {item.item_id: item for item in day.timeline}
        remove_names: set[str] = set()
        trim_day = False
        for issue in issues:
            item = timeline_by_id.get(issue.item_id or "")
            if issue.code in _REMOVE_ITEM_CODES and item and item.reference_name:
                remove_names.add(item.reference_name)
            if issue.code == "impossible_local_route" and issue.item_id:
                name = _next_attraction_name(day, issue.item_id)
                if name:
                    remove_names.add(name)
            if issue.code in _TRIM_DAY_CODES:
                trim_day = True
        remaining = [
            item
            for item in day.attractions
            if item.name not in remove_names or _is_must_visit(item.name, must_visit)
        ]
        if trim_day:
            removable_index = next(
                (
                    index
                    for index in range(len(remaining) - 1, -1, -1)
                    if not _is_must_visit(remaining[index].name, must_visit)
                ),
                None,
            )
            if removable_index is not None:
                remaining.pop(removable_index)
        city = expected_cities[day.day_index] if day.day_index < len(expected_cities) else day.city
        revised_days.append(day.model_copy(update={"city": city, "attractions": remaining}))
    return revised_days


def _reduce_budget(
    plan: TripPlanV2,
    days: list[DayPlanV2],
    must_visit: list[str],
) -> list[DayPlanV2]:
    if not any(issue.code == "budget_exceeded" for issue in plan.validation_report.issues):
        return days
    candidates = [
        (attraction.ticket_price, day_index, attraction.name)
        for day_index, day in enumerate(days)
        for attraction in day.attractions
        if attraction.ticket_price > 0 and not _is_must_visit(attraction.name, must_visit)
    ]
    if candidates:
        _, day_index, name = max(candidates)
        day = days[day_index]
        days[day_index] = day.model_copy(
            update={"attractions": [item for item in day.attractions if item.name != name]}
        )
        return days
    hotel_candidates = [
        (day.hotel.estimated_cost, day_index)
        for day_index, day in enumerate(days[:-1])
        if day.hotel and day.hotel.estimated_cost > 0
    ]
    if hotel_candidates:
        _, day_index = max(hotel_candidates)
        days[day_index] = days[day_index].model_copy(update={"hotel": None})
    return days


def revise_plan(state: TripState) -> dict[str, Any]:
    """Apply one bounded revision pass to critical problem areas only."""
    plan = state["draft_plan"]
    request = state["request"]
    days = _revise_days(state, plan)
    days = _reduce_budget(plan, days, [_place_key(value) for value in request.must_visit])
    revision_count = state.get("revision_count", 0) + 1
    revised = plan.model_copy(
        update={
            "city": request.destinations[0].city,
            "cities": [item.city for item in request.destinations],
            "start_date": request.start_date,
            "end_date": request.end_date,
            "days": days,
            "revision_count": revision_count,
        }
    )
    return {
        "draft_plan": revised,
        "revision_count": revision_count,
        "metrics": {
            **state.get("metrics", {}),
            "revised": True,
            "revision_count": revision_count,
        },
    }
