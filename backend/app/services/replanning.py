"""Deterministic impact analysis, scoped plan edits, and structured diffs."""

from __future__ import annotations

from typing import Any

from ..domain.review_models import (
    ImpactScopeV2,
    PlanDiffEntryV2,
    PlanDiffV2,
    ReplanRequestV2,
)
from ..domain.trip_models import TripPlanV2, TripRequestV2
from ..domain.validation_models import ValidationReportV2


def analyze_impact(
    request: ReplanRequestV2,
    plan: TripPlanV2,
) -> ImpactScopeV2:
    """Map typed user changes to the smallest deterministic refresh scope."""
    all_days = [day.day_index for day in plan.days]
    selected_days = set(request.day_indices or all_days)
    if request.transport_preferences is not None:
        selected_days.update(
            day.day_index for day in plan.days if day.is_transfer_day
        )
    fields: list[str] = []
    refresh_routing = request.transport_preferences is not None
    attraction_change = bool(request.add_attractions or request.remove_attractions)
    instruction_change = not any(
        (
            request.transport_preferences is not None,
            request.budget_total is not None,
            request.pace is not None,
            attraction_change,
        )
    )
    if request.transport_preferences is not None:
        fields.append("transport")
    if request.budget_total is not None:
        fields.append("budget")
    if request.pace is not None:
        fields.append("pace")
    if attraction_change:
        fields.append("attractions")
    if instruction_change:
        fields.append("instruction")
    return ImpactScopeV2(
        day_indices=sorted(selected_days),
        fields=fields,
        refresh_research=request.refresh_sources,
        refresh_routing=refresh_routing,
        rebuild_timeline=bool(
            attraction_change
            or instruction_change
            or request.pace is not None
            or request.transport_preferences is not None
        ),
        recalculate_budget=True,
    )


def apply_scoped_changes(
    *,
    trip_request: TripRequestV2,
    base_plan: TripPlanV2,
    change_request: ReplanRequestV2,
    impact_scope: ImpactScopeV2,
    route_estimates: list[Any] | None = None,
    transport_options: list[Any] | None = None,
    source_evidence: list[Any] | None = None,
) -> tuple[TripRequestV2, TripPlanV2, list[str]]:
    """Apply explicit fields while preserving all days outside the impact scope."""
    request_updates: dict[str, Any] = {}
    if change_request.transport_preferences is not None:
        request_updates["transport_preferences"] = change_request.transport_preferences
    if change_request.budget_total is not None:
        request_updates["budget_total"] = change_request.budget_total
    if change_request.pace is not None:
        request_updates["pace"] = change_request.pace
    updated_request = trip_request.model_copy(update=request_updates)

    known_attractions = {
        attraction.name.casefold(): attraction
        for day in base_plan.days
        for attraction in day.attractions
    }
    selected = set(impact_scope.day_indices)
    remove_names = {name.casefold() for name in change_request.remove_attractions}
    unresolved_additions: list[str] = []
    days = []
    for day in base_plan.days:
        if day.day_index not in selected:
            days.append(day)
            continue
        attractions = [
            attraction
            for attraction in day.attractions
            if attraction.name.casefold() not in remove_names
        ]
        existing = {item.name.casefold() for item in attractions}
        for name in change_request.add_attractions:
            candidate = known_attractions.get(name.casefold())
            if candidate is not None and candidate.name.casefold() not in existing:
                attractions.append(candidate)
                existing.add(candidate.name.casefold())
            elif candidate is None:
                unresolved_additions.append(name)

        instruction = change_request.instruction.casefold()
        asks_for_lighter_day = any(
            marker in instruction
            for marker in ("减少", "少安排", "轻松", "休息", "lighter", "less", "relax")
        )
        if (change_request.pace == "relaxed" or asks_for_lighter_day) and attractions:
            attractions = attractions[:-1]

        updates: dict[str, Any] = {"attractions": attractions, "timeline": []}
        if change_request.transport_preferences:
            updates["transportation"] = change_request.transport_preferences[0]
        days.append(day.model_copy(update=updates))

    merged_sources = list(base_plan.source_evidence)
    known_source_ids = {str(item.id) for item in merged_sources}
    for source in source_evidence or []:
        if str(source.id) not in known_source_ids:
            merged_sources.append(source)
            known_source_ids.add(str(source.id))

    plan_updates: dict[str, Any] = {
        "origin": updated_request.origin,
        "city": updated_request.destinations[0].city,
        "cities": [item.city for item in updated_request.destinations],
        "start_date": updated_request.start_date,
        "end_date": updated_request.end_date,
        "days": days,
        "source_evidence": merged_sources,
        "validation_report": ValidationReportV2(),
        "revision_count": 0,
    }
    if route_estimates is not None:
        plan_updates["route_matrix"] = route_estimates
    if transport_options is not None:
        plan_updates["transport_options"] = transport_options
    return updated_request, base_plan.model_copy(update=plan_updates), unresolved_additions


def diff_plans(
    before: TripPlanV2,
    after: TripPlanV2,
    *,
    from_version: int | None = None,
    to_version: int | None = None,
) -> PlanDiffV2:
    """Return a bounded semantic diff suitable for API and frontend rendering."""
    entries: list[PlanDiffEntryV2] = []
    changed_days: list[int] = []
    unchanged_days: list[int] = []

    _append_replace(entries, "/transport_options", before.transport_options, after.transport_options)
    _append_replace(entries, "/budget", before.budget, after.budget)
    _append_replace(
        entries,
        "/overall_suggestions",
        before.overall_suggestions,
        after.overall_suggestions,
    )
    _append_replace(entries, "/research_status", before.research_status, after.research_status)

    before_days = {day.day_index: day for day in before.days}
    after_days = {day.day_index: day for day in after.days}
    for day_index in sorted(set(before_days) | set(after_days)):
        old = before_days.get(day_index)
        new = after_days.get(day_index)
        if old is None:
            changed_days.append(day_index)
            entries.append(
                PlanDiffEntryV2(path=f"/days/{day_index}", operation="add", after=new)
            )
            continue
        if new is None:
            changed_days.append(day_index)
            entries.append(
                PlanDiffEntryV2(path=f"/days/{day_index}", operation="remove", before=old)
            )
            continue
        if old == new:
            unchanged_days.append(day_index)
            continue
        changed_days.append(day_index)
        prefix = f"/days/{day_index}"
        _append_replace(entries, f"{prefix}/city", old.city, new.city)
        _append_replace(entries, f"{prefix}/transportation", old.transportation, new.transportation)
        _append_replace(
            entries,
            f"{prefix}/attractions",
            [item.name for item in old.attractions],
            [item.name for item in new.attractions],
        )
        _append_replace(
            entries,
            f"{prefix}/timeline",
            [_timeline_signature(item) for item in old.timeline],
            [_timeline_signature(item) for item in new.timeline],
        )
        _append_replace(
            entries,
            f"{prefix}/arrangement_rationale",
            old.arrangement_rationale,
            new.arrangement_rationale,
        )

    _append_replace(
        entries,
        "/validation_report",
        before.validation_report,
        after.validation_report,
    )
    summary = (
        f"Changed {len(changed_days)} day(s) and preserved {len(unchanged_days)} day(s); "
        f"{len(entries)} structured field change(s)."
    )
    return PlanDiffV2(
        from_version=from_version,
        to_version=to_version,
        summary=summary,
        changed_day_indices=changed_days,
        unchanged_day_indices=unchanged_days,
        entries=entries[:500],
    )


def _append_replace(
    entries: list[PlanDiffEntryV2],
    path: str,
    before: Any,
    after: Any,
) -> None:
    if before == after:
        return
    entries.append(
        PlanDiffEntryV2(
            path=path,
            operation="replace",
            before=_json_value(before),
            after=_json_value(after),
        )
    )


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _timeline_signature(item: Any) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "type": item.item_type,
        "title": item.title,
        "start": item.start.isoformat(),
        "end": item.end.isoformat(),
        "duration_minutes": item.duration_minutes,
        "estimated_cost": item.estimated_cost,
    }
