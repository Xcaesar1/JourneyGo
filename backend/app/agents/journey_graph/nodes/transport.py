"""Deterministic intercity transport planning node."""

from __future__ import annotations

from hashlib import sha256
from math import ceil
from typing import Any

from ....domain.trip_models import IntercityTransportOptionV2, RouteEstimateV2
from ....services.routing import RouteEstimateProvider
from ..state import TripState

TransportMode = str


def _stable_option_id(leg_index: int, origin: str, destination: str, mode: str) -> str:
    value = f"{leg_index}\0{origin}\0{destination}\0{mode}"
    return f"transport-{sha256(value.encode()).hexdigest()[:20]}"


def _preferred_modes(preferences: list[str]) -> list[TransportMode]:
    modes: list[TransportMode] = []
    mappings = (
        (("flight", "air", "飞机", "航空"), "flight"),
        (("train", "rail", "高铁", "火车"), "train"),
        (("drive", "car", "自驾"), "driving"),
        (("coach", "bus", "大巴", "长途"), "coach"),
        (("public", "transit", "公共交通"), "public_transit"),
    )
    for preference in preferences:
        normalized = preference.casefold()
        for keywords, mode in mappings:
            if any(keyword in normalized for keyword in keywords) and mode not in modes:
                modes.append(mode)
    return modes


def _distance_modes(distance_meters: int | None) -> list[TransportMode]:
    if distance_meters is None:
        return ["train", "flight"]
    distance_km = distance_meters / 1000
    if distance_km <= 50:
        return ["public_transit", "driving"]
    if distance_km <= 500:
        return ["train", "driving"]
    if distance_km <= 1200:
        return ["train", "flight"]
    return ["flight", "train"]


def _duration_minutes(mode: TransportMode, estimate: RouteEstimateV2) -> int | None:
    if estimate.distance_meters is None:
        return None
    distance_km = estimate.distance_meters / 1000
    if mode == "flight":
        return ceil(180 + distance_km / 700 * 60)
    if mode == "train":
        return ceil(60 + distance_km / 200 * 60)
    if mode == "coach":
        return ceil(30 + distance_km / 70 * 60)
    if mode == "driving" and estimate.duration_minutes is not None:
        return estimate.duration_minutes
    if mode == "public_transit":
        return ceil(30 + distance_km / 35 * 60)
    return ceil(distance_km / 70 * 60)


def _cost_per_person(mode: TransportMode, estimate: RouteEstimateV2) -> int | None:
    if estimate.distance_meters is None:
        return None
    distance_km = estimate.distance_meters / 1000
    rates = {
        "flight": (500, 0.8),
        "train": (50, 0.5),
        "coach": (30, 0.3),
        "driving": (20, 0.65),
        "public_transit": (5, 0.2),
    }
    minimum, rate = rates[mode]
    return ceil(max(minimum, distance_km * rate))


def _advice(mode: TransportMode, origin: str, destination: str, language: str) -> str:
    labels = {
        "flight": "飞机",
        "train": "铁路",
        "coach": "长途客运",
        "driving": "自驾",
        "public_transit": "公共交通",
    }
    if language.casefold().startswith("zh"):
        return f"建议优先比较{origin}至{destination}的{labels[mode]}方案，并在预订前核对官方时刻与票价。"
    return (
        f"Compare {mode.replace('_', ' ')} options from {origin} to {destination}; "
        "verify official schedules and fares before booking."
    )


def _options_for_leg(
    *,
    leg_index: int,
    estimate: RouteEstimateV2,
    preferences: list[str],
    currency: str,
    language: str,
) -> list[IntercityTransportOptionV2]:
    modes = _preferred_modes(preferences)
    for mode in _distance_modes(estimate.distance_meters):
        if mode not in modes:
            modes.append(mode)
    modes = modes[:2]
    caveat = (
        "规划估算不代表具体车次、航班、发车时间、实时余票或实时价格。"
        if language.casefold().startswith("zh")
        else "Planning estimates are not train or flight numbers, departure times, live availability, or live fares."
    )
    return [
        IntercityTransportOptionV2(
            option_id=_stable_option_id(
                leg_index,
                estimate.origin,
                estimate.destination,
                mode,
            ),
            leg_index=leg_index,
            origin=estimate.origin,
            destination=estimate.destination,
            mode=mode,
            recommended=option_index == 0,
            estimated_duration_minutes=_duration_minutes(mode, estimate),
            estimated_cost_per_person=_cost_per_person(mode, estimate),
            currency=currency,
            route_estimate_id=estimate.estimate_id,
            estimate_status=("unavailable" if estimate.status == "unavailable" else "estimated"),
            advice=_advice(mode, estimate.origin, estimate.destination, language),
            caveats=[caveat],
        )
        for option_index, mode in enumerate(modes)
    ]


def make_plan_intercity_transport_node(provider: RouteEstimateProvider):
    """Build all origin/destination and destination/destination transport legs."""

    def plan_intercity_transport(state: TripState) -> dict[str, Any]:
        request = state["request"]
        locations = [request.origin, *(item.city for item in request.destinations)]
        route_estimates: list[RouteEstimateV2] = []
        transport_options: list[IntercityTransportOptionV2] = []
        for leg_index, (origin, destination) in enumerate(zip(locations, locations[1:])):
            estimate = provider.estimate(origin, destination)
            route_estimates.append(estimate)
            transport_options.extend(
                _options_for_leg(
                    leg_index=leg_index,
                    estimate=estimate,
                    preferences=request.transport_preferences,
                    currency=request.currency,
                    language=request.language,
                )
            )
        return {
            "route_estimates": route_estimates,
            "transport_options": transport_options,
            "metrics": {
                **state.get("metrics", {}),
                "transport_planned": True,
                "transport_leg_count": len(route_estimates),
                "route_unavailable_count": sum(
                    item.status == "unavailable" for item in route_estimates
                ),
            },
        }

    return plan_intercity_transport
