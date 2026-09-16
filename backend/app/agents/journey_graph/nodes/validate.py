"""Deterministic itinerary validation rules."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from ....domain.trip_models import DayPlanV2, ScheduleItemV2, TripPlanV2
from ....domain.validation_models import ValidationIssueV2, ValidationReportV2
from ..state import TripState


def _issue(
    code: str,
    severity: str,
    message: str,
    *,
    day_index: int | None = None,
    item: ScheduleItemV2 | None = None,
    evidence_ids: list[str] | None = None,
    action: str | None = None,
) -> ValidationIssueV2:
    return ValidationIssueV2(
        code=code,
        severity=severity,
        day_index=day_index,
        item_id=item.item_id if item else None,
        message=message,
        evidence_ids=evidence_ids or [],
        suggested_action=action,
    )


def _expected_cities(state: TripState) -> list[str]:
    return [
        destination.city
        for destination in state["request"].destinations
        for _ in range(destination.days)
    ]


def _validate_structure_and_dates(state: TripState, plan: TripPlanV2) -> list[ValidationIssueV2]:
    request = state["request"]
    issues: list[ValidationIssueV2] = []
    if plan.start_date != request.start_date or plan.end_date != request.end_date:
        issues.append(
            _issue(
                "date_window_mismatch",
                "critical",
                "Plan dates do not match the requested trip window.",
                action="Regenerate the plan using the normalized request dates.",
            )
        )
    expected_cities = _expected_cities(state)
    if len(plan.days) != request.travel_days:
        issues.append(
            _issue(
                "day_count_mismatch",
                "critical",
                "The number of itinerary days does not match the request.",
                action="Create exactly one day per requested date.",
            )
        )
    all_item_ids: list[str] = []
    seen_attractions: dict[str, int] = {}
    previous_city = request.origin
    for index, day in enumerate(plan.days):
        if index < len(expected_cities) and day.city != expected_cities[index]:
            issues.append(
                _issue(
                    "day_city_mismatch",
                    "critical",
                    f"Day {index + 1} is assigned to {day.city}, expected {expected_cities[index]}.",
                    day_index=index,
                    action="Align each day with the requested destination stay allocation.",
                )
            )
        expected_transfer = day.city != previous_city
        if expected_transfer and not day.is_transfer_day:
            issues.append(
                _issue(
                    "missing_transfer_marker",
                    "critical",
                    f"Day {index + 1} changes location from {previous_city} to {day.city} without a transfer marker.",
                    day_index=index,
                    action="Mark the day as a transfer day and include the intercity transport item.",
                )
            )
        previous_city = day.city
        all_item_ids.extend(item.item_id for item in day.timeline)
        for attraction in day.attractions:
            key = attraction.name.casefold()
            if key in seen_attractions:
                issues.append(
                    _issue(
                        "duplicate_attraction",
                        "warning",
                        f"{attraction.name} appears on more than one day.",
                        day_index=index,
                        action="Replace the duplicate unless a repeat visit is intentional.",
                    )
                )
            else:
                seen_attractions[key] = index
    if len(all_item_ids) != len(set(all_item_ids)):
        issues.append(
            _issue(
                "duplicate_item_id",
                "critical",
                "Timeline item_id values must be unique across the trip.",
                action="Regenerate deterministic item identifiers.",
            )
        )
    return issues


def _validate_time(state: TripState, plan: TripPlanV2) -> list[ValidationIssueV2]:
    request = state["request"]
    issues: list[ValidationIssueV2] = []
    for day in plan.days:
        expected_start = datetime.combine(day.date, request.daily_start_time)
        expected_end = datetime.combine(day.date, request.daily_end_time)
        if not day.timeline:
            issues.append(
                _issue(
                    "empty_timeline",
                    "critical",
                    "The day has no executable timeline.",
                    day_index=day.day_index,
                    action="Create a contiguous timeline for the full day window.",
                )
            )
            continue
        if day.timeline[0].start != expected_start:
            issues.append(
                _issue(
                    "timeline_start_mismatch",
                    "critical",
                    "The daily timeline does not start at the requested time.",
                    day_index=day.day_index,
                    item=day.timeline[0],
                    action="Start the first item at the requested daily start time.",
                )
            )
        for item in day.timeline:
            actual_duration = round((item.end - item.start).total_seconds() / 60)
            if item.end <= item.start or item.duration_minutes != actual_duration:
                issues.append(
                    _issue(
                        "invalid_item_duration",
                        "critical",
                        f"{item.title} has inconsistent start, end, or duration values.",
                        day_index=day.day_index,
                        item=item,
                        action="Recalculate the item end time from start plus duration.",
                    )
                )
            if item.start.date() != day.date:
                issues.append(
                    _issue(
                        "item_outside_day",
                        "critical",
                        f"{item.title} starts outside its itinerary date.",
                        day_index=day.day_index,
                        item=item,
                        action="Move the item into the assigned day.",
                    )
                )
        for left, right in zip(day.timeline, day.timeline[1:]):
            if left.end != right.start:
                severity = "critical" if left.end > right.start else "warning"
                issues.append(
                    _issue(
                        "timeline_overlap" if severity == "critical" else "timeline_gap",
                        severity,
                        f"Timeline discontinuity between {left.title} and {right.title}.",
                        day_index=day.day_index,
                        item=right,
                        action="Rebuild the day as a contiguous sequence.",
                    )
                )
        if day.timeline[-1].end > expected_end:
            issues.append(
                _issue(
                    "daily_window_exceeded",
                    "critical",
                    "The daily timeline ends after the requested daily end time.",
                    day_index=day.day_index,
                    item=day.timeline[-1],
                    action="Remove or shorten lower-priority activities.",
                )
            )
        elif day.timeline[-1].end < expected_end:
            issues.append(
                _issue(
                    "timeline_not_closed",
                    "warning",
                    "The timeline does not account for the full requested day window.",
                    day_index=day.day_index,
                    action="Add an explicit flexible-time buffer.",
                )
            )
        issues.extend(_validate_meal_times(day))
    return issues


def _validate_meal_times(day: DayPlanV2) -> list[ValidationIssueV2]:
    windows = {
        "breakfast": (6 * 60, 10 * 60 + 30),
        "lunch": (10 * 60 + 30, 14 * 60 + 30),
        "dinner": (16 * 60 + 30, 21 * 60 + 30),
    }
    meal_types = {meal.name: meal.type for meal in day.meals}
    issues: list[ValidationIssueV2] = []
    for item in day.timeline:
        meal_type = meal_types.get(item.reference_name or "")
        if item.item_type != "meal" or meal_type not in windows:
            continue
        minute = item.start.hour * 60 + item.start.minute
        start, end = windows[meal_type]
        if not start <= minute <= end:
            issues.append(
                _issue(
                    "meal_time_unreasonable",
                    "warning",
                    f"{item.title} is scheduled outside the usual {meal_type} window.",
                    day_index=day.day_index,
                    item=item,
                    action="Move the meal into a practical time window.",
                )
            )
    return issues


def _validate_routes(state: TripState, plan: TripPlanV2) -> list[ValidationIssueV2]:
    request = state["request"]
    route_by_id = {route.estimate_id: route for route in plan.route_matrix}
    transport_options = plan.transport_options or list(state.get("transport_options", []))
    intercity_duration_by_route = {
        option.route_estimate_id: option.estimated_duration_minutes
        for option in transport_options
        if option.recommended
        and option.route_estimate_id is not None
        and option.estimated_duration_minutes is not None
    }
    issues: list[ValidationIssueV2] = []
    for day in plan.days:
        transport_minutes = 0
        walking_minutes = 0
        normalized_transport = day.transportation.casefold()
        for item in day.timeline:
            if item.item_type != "transport":
                continue
            transport_minutes += item.duration_minutes
            if "walk" in normalized_transport or "步行" in normalized_transport:
                walking_minutes += item.duration_minutes
            route = route_by_id.get(item.route_estimate_id or "")
            if route is None:
                issues.append(
                    _issue(
                        "missing_route_estimate",
                        "critical",
                        f"{item.title} has no matching route estimate.",
                        day_index=day.day_index,
                        item=item,
                        action="Fetch or calculate a route before finalizing the timeline.",
                    )
                )
                continue
            if route.status == "unavailable":
                issues.append(
                    _issue(
                        "route_data_unavailable",
                        "warning",
                        f"Distance or duration is unavailable for {item.title}.",
                        day_index=day.day_index,
                        item=item,
                        action="Verify this transfer manually before departure.",
                    )
                )
            expected_duration = intercity_duration_by_route.get(
                route.estimate_id,
                route.duration_minutes,
            )
            if expected_duration is not None and item.duration_minutes < expected_duration:
                issues.append(
                    _issue(
                        "route_duration_underallocated",
                        "critical",
                        f"{item.title} allocates less time than its route estimate.",
                        day_index=day.day_index,
                        item=item,
                        action="Increase transfer time or remove a later activity.",
                    )
                )
            if (
                route.provider == "local-estimate"
                and route.distance_meters is not None
                and route.distance_meters > 250_000
            ):
                issues.append(
                    _issue(
                        "impossible_local_route",
                        "critical",
                        f"A same-day local transfer is approximately {route.distance_meters // 1000} km.",
                        day_index=day.day_index,
                        item=item,
                        action="Move the activity to another city/day or replace it.",
                    )
                )
        commute_limit = 600 if day.is_transfer_day else 180
        if transport_minutes > commute_limit:
            issues.append(
                _issue(
                    "daily_commute_excessive",
                    "critical",
                    f"Day {day.day_index + 1} contains {transport_minutes} minutes of transport.",
                    day_index=day.day_index,
                    action="Reduce transfers or split the route across days.",
                )
            )
        elif not day.is_transfer_day and transport_minutes > 120:
            issues.append(
                _issue(
                    "daily_commute_high",
                    "warning",
                    f"Day {day.day_index + 1} contains substantial local transport.",
                    day_index=day.day_index,
                    action="Reorder nearby places to reduce commuting.",
                )
            )
        walking_limit = request.max_daily_walking_minutes
        if walking_limit is not None and walking_minutes > walking_limit:
            severity = "critical" if walking_minutes > walking_limit * 1.5 else "warning"
            issues.append(
                _issue(
                    "walking_limit_exceeded",
                    severity,
                    f"Estimated walking time exceeds the requested {walking_limit}-minute limit.",
                    day_index=day.day_index,
                    action="Use transit or replace distant activities.",
                )
            )
    return issues


def _validate_budget(state: TripState, plan: TripPlanV2) -> list[ValidationIssueV2]:
    budget = plan.budget
    if budget is None:
        return [
            _issue(
                "budget_missing",
                "critical",
                "The plan has no program-calculated budget.",
                action="Recalculate all budget categories.",
            )
        ]
    components = (
        budget.total_attractions
        + budget.total_hotels
        + budget.total_meals
        + budget.total_transportation
        + budget.total_inter_city_transport
    )
    issues: list[ValidationIssueV2] = []
    if budget.total != components:
        issues.append(
            _issue(
                "budget_total_mismatch",
                "critical",
                "Budget category totals do not add up to the reported total.",
                action="Replace the total with the deterministic category sum.",
            )
        )
    requested_budget = state["request"].budget_total
    if requested_budget is not None and Decimal(budget.total) > requested_budget:
        ratio = Decimal(budget.total) / requested_budget
        severity = "critical" if ratio > Decimal("1.10") else "warning"
        issues.append(
            _issue(
                "budget_exceeded",
                severity,
                f"Calculated cost {budget.total} exceeds the requested budget {requested_budget}.",
                action="Replace costly items or increase the budget.",
            )
        )
    if any(
        option.recommended and option.estimated_cost_per_person is None
        for option in plan.transport_options
    ):
        issues.append(
            _issue(
                "transport_cost_unknown",
                "info",
                "At least one recommended intercity leg has no reliable cost estimate.",
                action="Check official fares before booking.",
            )
        )
    return issues


def _validate_opening_hours(plan: TripPlanV2) -> list[ValidationIssueV2]:
    issues: list[ValidationIssueV2] = []
    for day in plan.days:
        for item in day.timeline:
            if item.item_type != "attraction":
                continue
            if day.date in item.closed_dates:
                issues.append(
                    _issue(
                        "attraction_closed",
                        "critical",
                        f"{item.title} is marked closed on {day.date.isoformat()}.",
                        day_index=day.day_index,
                        item=item,
                        evidence_ids=item.source_evidence_ids,
                        action="Move the visit to an open date or choose an alternative.",
                    )
                )
            if item.opening_time and item.start.time() < item.opening_time:
                issues.append(
                    _issue(
                        "before_opening_time",
                        "critical",
                        f"{item.title} starts before its opening time.",
                        day_index=day.day_index,
                        item=item,
                        evidence_ids=item.source_evidence_ids,
                        action="Move the visit after opening time.",
                    )
                )
            if item.closing_time and item.end.time() > item.closing_time:
                issues.append(
                    _issue(
                        "after_closing_time",
                        "critical",
                        f"{item.title} ends after its closing time.",
                        day_index=day.day_index,
                        item=item,
                        evidence_ids=item.source_evidence_ids,
                        action="Move or shorten the visit.",
                    )
                )
            if not item.opening_time or not item.closing_time:
                issues.append(
                    _issue(
                        "opening_hours_unverified",
                        "info",
                        f"Opening hours are not verified for {item.title}.",
                        day_index=day.day_index,
                        item=item,
                        evidence_ids=item.source_evidence_ids,
                        action="Confirm official opening hours before departure.",
                    )
                )
    return issues


def _validate_intensity(state: TripState, plan: TripPlanV2) -> list[ValidationIssueV2]:
    pace = state["request"].pace
    warning_limits = {"relaxed": 3, "balanced": 4, "intensive": 6}
    critical_limits = {"relaxed": 4, "balanced": 5, "intensive": 7}
    issues: list[ValidationIssueV2] = []
    for day in plan.days:
        attraction_count = len(day.attractions)
        if attraction_count > critical_limits[pace]:
            issues.append(
                _issue(
                    "daily_intensity_excessive",
                    "critical",
                    f"Day {day.day_index + 1} has {attraction_count} attractions for a {pace} pace.",
                    day_index=day.day_index,
                    action="Remove lower-priority attractions.",
                )
            )
        elif attraction_count > warning_limits[pace]:
            issues.append(
                _issue(
                    "daily_intensity_high",
                    "warning",
                    f"Day {day.day_index + 1} is dense for a {pace} pace.",
                    day_index=day.day_index,
                    action="Confirm the pace or remove one attraction.",
                )
            )
        if day.is_transfer_day and attraction_count > 2:
            severity = "critical" if attraction_count > 3 else "warning"
            issues.append(
                _issue(
                    "transfer_day_overloaded",
                    severity,
                    "A transfer day contains too many attractions.",
                    day_index=day.day_index,
                    action="Keep only one or two nearby activities on transfer days.",
                )
            )
    return issues


def validate_plan(state: TripState) -> dict[str, Any]:
    """Run all deterministic rules and attach the report to the plan output."""
    plan = state["draft_plan"]
    issues = [
        *_validate_structure_and_dates(state, plan),
        *_validate_time(state, plan),
        *_validate_routes(state, plan),
        *_validate_budget(state, plan),
        *_validate_opening_hours(plan),
        *_validate_intensity(state, plan),
    ]
    report = ValidationReportV2(issues=issues)
    validated_plan = plan.model_copy(
        update={
            "validation_report": report,
            "revision_count": state.get("revision_count", 0),
        }
    )
    return {
        "draft_plan": validated_plan,
        "validation_report": report,
        "metrics": {
            **state.get("metrics", {}),
            "validated": True,
            "validation_critical_count": sum(item.severity == "critical" for item in issues),
            "validation_warning_count": sum(item.severity == "warning" for item in issues),
            "validation_info_count": sum(item.severity == "info" for item in issues),
        },
    }


# Preserve the Phase 3 import while callers migrate to the final node name.
validate_stub = validate_plan
