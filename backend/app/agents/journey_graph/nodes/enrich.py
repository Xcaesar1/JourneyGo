"""Deterministic timeline enrichment and budget calculation."""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from math import asin, ceil, cos, radians, sin, sqrt
from typing import Any

from ....domain.trip_models import (
    AttractionV2,
    BudgetV2,
    DayPlanV2,
    LocationV2,
    MealV2,
    RouteEstimateV2,
    ScheduleItemV2,
    TripPlanV2,
)
from ....services.routing.providers import route_estimate_id
from ..state import TripState


def _item_id(day_index: int, item_type: str, position: int, name: str) -> str:
    digest = sha256(f"{day_index}\0{item_type}\0{position}\0{name}".encode()).hexdigest()[:16]
    return f"day-{day_index}-{item_type}-{digest}"


def _ordered_activities(day: DayPlanV2) -> list[tuple[str, AttractionV2 | MealV2]]:
    meals = {meal.type: meal for meal in day.meals}
    attractions = list(day.attractions)
    midpoint = ceil(len(attractions) / 2)
    ordered: list[tuple[str, AttractionV2 | MealV2]] = []
    if "breakfast" in meals:
        ordered.append(("meal", meals["breakfast"]))
    ordered.extend(("attraction", item) for item in attractions[:midpoint])
    if "lunch" in meals:
        ordered.append(("meal", meals["lunch"]))
    if "snack" in meals:
        ordered.append(("meal", meals["snack"]))
    ordered.extend(("attraction", item) for item in attractions[midpoint:])
    if "dinner" in meals:
        ordered.append(("meal", meals["dinner"]))
    return ordered


def _haversine_meters(origin: LocationV2, destination: LocationV2) -> int:
    earth_radius = 6_371_000
    lat1, lon1 = radians(origin.latitude), radians(origin.longitude)
    lat2, lon2 = radians(destination.latitude), radians(destination.longitude)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return round(earth_radius * 2 * asin(sqrt(value)))


def _local_route(
    day: DayPlanV2,
    origin_name: str,
    origin: LocationV2 | None,
    destination_name: str,
    destination: LocationV2 | None,
) -> RouteEstimateV2:
    route_origin = f"{day.city}: {origin_name}"
    route_destination = f"{day.city}: {destination_name}"
    estimate_id = route_estimate_id("local-estimate", route_origin, route_destination)
    if origin is None or destination is None:
        return RouteEstimateV2(
            estimate_id=estimate_id,
            origin=route_origin,
            destination=route_destination,
            mode="straight_line",
            provider="local-estimate",
            status="unavailable",
            detail="Coordinates are missing; a conservative transfer allowance is used.",
        )
    straight_line = _haversine_meters(origin, destination)
    route_distance = ceil(straight_line * 1.3)
    normalized_transport = day.transportation.casefold()
    if "walk" in normalized_transport or "步行" in normalized_transport:
        speed_kmh = 4.5
    elif "drive" in normalized_transport or "自驾" in normalized_transport:
        speed_kmh = 30
    else:
        speed_kmh = 20
    duration = max(5, ceil(route_distance / 1000 / speed_kmh * 60 + 8))
    return RouteEstimateV2(
        estimate_id=estimate_id,
        origin=route_origin,
        destination=route_destination,
        mode="straight_line",
        distance_meters=route_distance,
        duration_minutes=duration,
        provider="local-estimate",
        status="estimated",
        detail="Estimated from coordinates with a road-distance and transfer buffer.",
    )


def _activity_duration(item_type: str, item: AttractionV2 | MealV2) -> int:
    if item_type == "attraction":
        return max(30, item.visit_duration)
    return 45 if item.type in {"breakfast", "snack"} else 60


def _activity_cost(item_type: str, item: AttractionV2 | MealV2) -> int:
    return item.ticket_price if item_type == "attraction" else item.estimated_cost


def _build_day_timeline(
    day: DayPlanV2,
    state: TripState,
) -> tuple[DayPlanV2, list[RouteEstimateV2], int]:
    request = state["request"]
    current = datetime.combine(day.date, request.daily_start_time)
    target_end = datetime.combine(day.date, request.daily_end_time)
    timeline: list[ScheduleItemV2] = []
    routes: list[RouteEstimateV2] = []
    local_transport_cost = 0
    previous_name: str | None = None
    previous_location: LocationV2 | None = None
    activities = _ordered_activities(day)

    transfer_leg_index: int | None = None
    day_offset = 0
    for destination_index, destination in enumerate(request.destinations):
        if day.day_index == day_offset:
            previous_city = request.origin if destination_index == 0 else request.destinations[destination_index - 1].city
            if previous_city != destination.city:
                transfer_leg_index = destination_index
            break
        day_offset += destination.days
    recommended_transfer = next(
        (
            option
            for option in state.get("transport_options", [])
            if option.leg_index == transfer_leg_index and option.recommended
        ),
        None,
    )
    if recommended_transfer is not None:
        transfer_minutes = recommended_transfer.estimated_duration_minutes or 120
        transfer_end = current + timedelta(minutes=transfer_minutes)
        timeline.append(
            ScheduleItemV2(
                item_id=_item_id(
                    day.day_index,
                    "transport",
                    -1,
                    recommended_transfer.option_id,
                ),
                item_type="transport",
                title=f"{recommended_transfer.origin} → {recommended_transfer.destination}",
                start=current,
                end=transfer_end,
                duration_minutes=transfer_minutes,
                route_estimate_id=recommended_transfer.route_estimate_id,
                estimated_cost=recommended_transfer.estimated_cost_per_person or 0,
            )
        )
        current = transfer_end

    for position, (item_type, activity) in enumerate(activities):
        if previous_name is not None:
            route = _local_route(
                day,
                previous_name,
                previous_location,
                activity.name,
                activity.location,
            )
            routes.append(route)
            transfer_minutes = route.duration_minutes or 30
            transfer_end = current + timedelta(minutes=transfer_minutes)
            transfer_cost = 0
            if route.distance_meters is not None:
                transfer_cost = max(2, ceil(route.distance_meters / 1000 * 0.2))
            local_transport_cost += transfer_cost
            timeline.append(
                ScheduleItemV2(
                    item_id=_item_id(day.day_index, "transport", position, route.estimate_id),
                    item_type="transport",
                    title=f"{previous_name} → {activity.name}",
                    start=current,
                    end=transfer_end,
                    duration_minutes=transfer_minutes,
                    route_estimate_id=route.estimate_id,
                    estimated_cost=transfer_cost,
                )
            )
            current = transfer_end

        duration = _activity_duration(item_type, activity)
        activity_end = current + timedelta(minutes=duration)
        opening_time = activity.opening_time if isinstance(activity, AttractionV2) else None
        closing_time = activity.closing_time if isinstance(activity, AttractionV2) else None
        closed_dates = activity.closed_dates if isinstance(activity, AttractionV2) else []
        evidence_ids = activity.source_evidence_ids if isinstance(activity, AttractionV2) else []
        timeline.append(
            ScheduleItemV2(
                item_id=_item_id(day.day_index, item_type, position, activity.name),
                item_type=item_type,
                title=activity.name,
                start=current,
                end=activity_end,
                duration_minutes=duration,
                location=activity.location,
                reference_name=activity.name,
                estimated_cost=_activity_cost(item_type, activity),
                opening_time=opening_time,
                closing_time=closing_time,
                closed_dates=closed_dates,
                source_evidence_ids=evidence_ids,
            )
        )
        current = activity_end
        previous_name = activity.name
        previous_location = activity.location

    if current < target_end:
        timeline.append(
            ScheduleItemV2(
                item_id=_item_id(day.day_index, "free_time", len(timeline), "day buffer"),
                item_type="free_time",
                title="Flexible time / rest",
                start=current,
                end=target_end,
                duration_minutes=round((target_end - current).total_seconds() / 60),
            )
        )
    elif not timeline:
        timeline.append(
            ScheduleItemV2(
                item_id=_item_id(day.day_index, "free_time", 0, "open day"),
                item_type="free_time",
                title="Flexible day",
                start=current,
                end=target_end,
                duration_minutes=round((target_end - current).total_seconds() / 60),
            )
        )

    language = request.language.casefold()
    rationale = (
        "按原推荐顺序串联活动，显式加入相邻地点交通，并把剩余时间保留为休息或机动时段。"
        if language.startswith("zh")
        else "Activities keep their recommended order, include explicit transfers, and preserve remaining time as a rest buffer."
    )
    update: dict[str, Any] = {
        "timeline": timeline,
        "arrangement_rationale": rationale,
    }
    if recommended_transfer is not None:
        update.update(
            {
                "is_transfer_day": True,
                "transfer_info": recommended_transfer.advice,
            }
        )
    return day.model_copy(update=update), routes, local_transport_cost


def _calculate_budget(
    plan: TripPlanV2,
    state: TripState,
    local_transport_per_person: int,
) -> BudgetV2:
    request = state["request"]
    travelers = request.travelers
    attraction_cost = sum(
        attraction.ticket_price
        for day in plan.days
        for attraction in day.attractions
    ) * travelers
    meal_cost = sum(meal.estimated_cost for day in plan.days for meal in day.meals) * travelers
    hotel_nights = plan.days[:-1]
    rooms = ceil(travelers / 2)
    hotel_cost = sum(day.hotel.estimated_cost for day in hotel_nights if day.hotel) * rooms
    local_transport_cost = local_transport_per_person * travelers
    recommended_by_leg = {
        option.leg_index: option
        for option in plan.transport_options
        if option.recommended
    }
    intercity_cost = sum(
        option.estimated_cost_per_person or 0 for option in recommended_by_leg.values()
    ) * travelers
    total = attraction_cost + hotel_cost + meal_cost + local_transport_cost + intercity_cost
    return BudgetV2(
        total_attractions=attraction_cost,
        total_hotels=hotel_cost,
        total_meals=meal_cost,
        total_transportation=local_transport_cost,
        total_inter_city_transport=intercity_cost,
        total=total,
    )


def enrich_plan(state: TripState) -> dict[str, Any]:
    """Replace model timelines and totals with deterministic program output."""
    plan = state["draft_plan"]
    days: list[DayPlanV2] = []
    daily_routes: list[RouteEstimateV2] = []
    local_transport_cost = 0
    for day in plan.days:
        enriched_day, routes, route_cost = _build_day_timeline(day, state)
        days.append(enriched_day)
        daily_routes.extend(routes)
        local_transport_cost += route_cost
    enriched = plan.model_copy(
        update={
            "days": days,
            "route_matrix": [*state.get("route_estimates", []), *daily_routes],
        }
    )
    enriched = enriched.model_copy(
        update={"budget": _calculate_budget(enriched, state, local_transport_cost)}
    )
    return {
        "draft_plan": enriched,
        "metrics": {
            **state.get("metrics", {}),
            "timeline_enriched": True,
            "timeline_item_count": sum(len(day.timeline) for day in days),
            "budget_recalculated": True,
        },
    }
