"""Convert typed JourneyGraph plans to the existing API and frontend contract."""

from __future__ import annotations

from ..domain.trip_models import LocationV2, TripPlanV2
from ..models.schemas import (
    Attraction,
    Budget,
    DayPlan,
    Hotel,
    Location,
    Meal,
    TripPlan,
    WeatherInfo,
)


def _location(location: LocationV2 | None) -> Location | None:
    if location is None:
        return None
    return Location(longitude=location.longitude, latitude=location.latitude)


def trip_plan_v2_to_legacy(plan: TripPlanV2) -> TripPlan:
    """Return the exact legacy TripPlan shape consumed by the current frontend."""
    days: list[DayPlan] = []
    for day in plan.days:
        attractions = [
            Attraction(
                name=item.name,
                address=item.address,
                location=Location(
                    longitude=item.location.longitude,
                    latitude=item.location.latitude,
                ),
                visit_duration=item.visit_duration,
                description=item.description,
                category=item.category,
                poi_id=item.poi_id,
                rating=item.rating,
                image_url=item.image_url or None,
                photos=[item.image_url] if item.image_url else [],
                image_source=item.image_source,
                image_author=item.image_author,
                image_license=item.image_license,
                image_source_page=item.image_source_page,
                image_attribution=item.image_attribution,
                recommendation_reason=item.recommendation_reason,
                ticket_price=item.ticket_price,
                reservation_required=item.reservation_required,
                reservation_tips=item.reservation_tips,
            )
            for item in day.attractions
            if item.location is not None
        ]
        meals = [
            Meal(
                type=item.type,
                name=item.name,
                address=item.address,
                location=_location(item.location),
                description=item.description,
                estimated_cost=item.estimated_cost,
            )
            for item in day.meals
        ]
        hotel = None
        if day.hotel is not None:
            hotel = Hotel(
                name=day.hotel.name,
                address=day.hotel.address,
                location=_location(day.hotel.location),
                price_range=day.hotel.price_range,
                rating=day.hotel.rating,
                distance=day.hotel.distance,
                type=day.hotel.type,
                estimated_cost=day.hotel.estimated_cost,
            )
        days.append(
            DayPlan(
                date=day.date.isoformat(),
                day_index=day.day_index,
                city=day.city,
                is_transfer_day=day.is_transfer_day,
                transfer_info=day.transfer_info,
                description=day.description,
                transportation=day.transportation,
                accommodation=day.accommodation,
                hotel=hotel,
                attractions=attractions,
                meals=meals,
                timeline=day.timeline,
                arrangement_rationale=day.arrangement_rationale,
            )
        )

    weather = [
        WeatherInfo(
            date=item.date.isoformat(),
            city=item.city,
            day_weather=item.day_weather,
            night_weather=item.night_weather,
            day_temp=item.day_temp,
            night_temp=item.night_temp,
            wind_direction=item.wind_direction,
            wind_power=item.wind_power,
        )
        for item in plan.weather_info
    ]
    budget = None
    if plan.budget is not None:
        budget = Budget(
            total_attractions=plan.budget.total_attractions,
            total_hotels=plan.budget.total_hotels,
            total_meals=plan.budget.total_meals,
            total_transportation=plan.budget.total_transportation,
            total_inter_city_transport=plan.budget.total_inter_city_transport,
            total=plan.budget.total,
        )
    return TripPlan(
        origin=plan.origin,
        city=plan.city,
        cities=plan.cities,
        start_date=plan.start_date.isoformat(),
        end_date=plan.end_date.isoformat(),
        days=days,
        transport_options=plan.transport_options,
        route_matrix=plan.route_matrix,
        weather_info=weather,
        overall_suggestions=plan.overall_suggestions,
        budget=budget,
        source_evidence=plan.source_evidence,
        research_updated_at=plan.research_updated_at,
        research_status=plan.research_status,
        validation_report=plan.validation_report,
        revision_count=plan.revision_count,
    )
