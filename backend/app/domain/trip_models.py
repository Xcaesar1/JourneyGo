"""Typed request models for the Phase 1 v2 API skeleton."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .research_models import SourceEvidence
from .validation_models import ValidationReportV2

TRIP_REQUEST_V2_EXAMPLE: dict[str, Any] = {
    "origin": "Shanghai",
    "destinations": [
        {"city": "Tokyo", "days": 3},
        {"city": "Kyoto", "days": 2},
    ],
    "start_date": "2026-10-10",
    "end_date": "2026-10-14",
    "travel_days": 5,
    "budget_total": "12000.00",
    "currency": "CNY",
    "travelers": 2,
    "transport_preferences": ["flight", "train"],
    "accommodation_preference": "midscale hotel",
    "interests": ["food", "museums"],
    "must_visit": ["Senso-ji"],
    "avoid": ["red-eye flights"],
    "pace": "balanced",
    "daily_start_time": "09:00:00",
    "daily_end_time": "21:00:00",
    "max_daily_walking_minutes": 180,
    "accessibility_needs": ["elevator access"],
    "free_text_input": "Keep the first day light after arrival.",
    "language": "en",
    "timezone": "Asia/Tokyo",
}

PreferenceText = Annotated[str, Field(min_length=1, max_length=120)]
PlaceText = Annotated[str, Field(min_length=1, max_length=200)]


class CityStayV2(BaseModel):
    """Requested stay duration for a single destination."""

    model_config = ConfigDict(str_strip_whitespace=True)

    city: str = Field(..., min_length=1, max_length=120, description="Destination city name.")
    days: int = Field(..., ge=1, le=30, description="Inclusive number of days spent in the city.")


class TripRequestV2(BaseModel):
    """Validated request contract for POST /api/v2/trips."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"example": TRIP_REQUEST_V2_EXAMPLE},
    )

    origin: str = Field(..., min_length=1, max_length=120, description="Trip origin.")
    destinations: list[CityStayV2] = Field(
        ...,
        min_length=1,
        max_length=12,
        description="Ordered destination list with inclusive stay lengths.",
    )
    start_date: date = Field(..., description="Trip start date.")
    end_date: date = Field(..., description="Trip end date.")
    travel_days: int = Field(..., ge=1, le=30, description="Inclusive trip length in days.")
    budget_total: Decimal | None = Field(
        default=None,
        gt=0,
        description="Optional total budget. Must be positive when provided.",
    )
    currency: str = Field(default="CNY", min_length=3, max_length=3, description="Budget currency.")
    travelers: int = Field(default=1, ge=1, le=20, description="Traveler count.")

    transport_preferences: list[PreferenceText] = Field(
        default_factory=list, max_length=8, description="Transport preferences."
    )
    accommodation_preference: str | None = Field(
        default=None,
        max_length=120,
        description="Accommodation preference.",
    )
    interests: list[PreferenceText] = Field(default_factory=list, max_length=30, description="Interest tags.")
    must_visit: list[PlaceText] = Field(default_factory=list, max_length=30, description="Must-visit places.")
    avoid: list[PlaceText] = Field(default_factory=list, max_length=30, description="Items to avoid.")

    pace: Literal["relaxed", "balanced", "intensive"] = Field(
        default="balanced",
        description="Daily pacing preference.",
    )
    daily_start_time: time = Field(default=time(9, 0), description="Preferred daily start time.")
    daily_end_time: time = Field(default=time(21, 0), description="Preferred daily end time.")
    max_daily_walking_minutes: int | None = Field(
        default=None,
        ge=0,
        le=1440,
        description="Optional walking limit per day.",
    )
    accessibility_needs: list[PreferenceText] = Field(
        default_factory=list, max_length=20, description="Accessibility requirements."
    )

    free_text_input: str = Field(default="", max_length=2000, description="Extra planning context.")
    language: str = Field(default="zh", min_length=2, max_length=8, description="Response language.")
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64, description="Trip timezone.")

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        """Normalize the currency code for downstream consumers."""
        return value.upper()

    @model_validator(mode="after")
    def validate_trip_window(self) -> TripRequestV2:
        """Apply cross-field validation for the v2 skeleton contract."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")

        inclusive_days = (self.end_date - self.start_date).days + 1
        if inclusive_days != self.travel_days:
            raise ValueError("travel_days must match the inclusive date range")

        destination_days = sum(destination.days for destination in self.destinations)
        if destination_days != self.travel_days:
            raise ValueError("destinations.days must sum to travel_days")

        if self.daily_end_time <= self.daily_start_time:
            raise ValueError("daily_end_time must be after daily_start_time")

        return self


class LocationV2(BaseModel):
    """Geographic coordinates returned by structured planning."""

    model_config = ConfigDict(extra="forbid")

    longitude: float = Field(..., ge=-180, le=180)
    latitude: float = Field(..., ge=-90, le=90)


class AttractionV2(BaseModel):
    """A typed attraction compatible with the existing result view."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    location: LocationV2 | None = None
    visit_duration: int = Field(default=60, ge=0, le=1440)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="attraction", max_length=120)
    poi_id: str = Field(default="", max_length=120)
    rating: float | None = Field(default=None, ge=0, le=5)
    image_url: str = Field(default="", max_length=2000)
    image_source: str = Field(default="", max_length=80)
    image_author: str = Field(default="", max_length=300)
    image_license: str = Field(default="", max_length=120)
    image_source_page: str = Field(default="", max_length=2000)
    image_attribution: str = Field(default="", max_length=1000)
    recommendation_reason: str = Field(default="", max_length=500)
    ticket_price: int = Field(default=0, ge=0)
    reservation_required: bool = False
    reservation_tips: str = Field(default="", max_length=1000)
    opening_time: time | None = None
    closing_time: time | None = None
    closed_dates: list[date] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)


class MealV2(BaseModel):
    """A typed meal recommendation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["breakfast", "lunch", "dinner", "snack"]
    name: str = Field(..., min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    location: LocationV2 | None = None
    description: str | None = Field(default=None, max_length=1000)
    estimated_cost: int = Field(default=0, ge=0)


class HotelV2(BaseModel):
    """A typed accommodation recommendation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    location: LocationV2 | None = None
    price_range: str = Field(default="", max_length=120)
    rating: str = Field(default="", max_length=32)
    distance: str = Field(default="", max_length=120)
    type: str = Field(default="", max_length=120)
    estimated_cost: int = Field(default=0, ge=0)


class ScheduleItemV2(BaseModel):
    """One contiguous item in a deterministic daily timeline."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_id: str = Field(..., min_length=1, max_length=100)
    item_type: Literal["attraction", "meal", "transport", "free_time"]
    title: str = Field(..., min_length=1, max_length=300)
    start: datetime
    end: datetime
    duration_minutes: int = Field(..., ge=0, le=2880)
    location: LocationV2 | None = None
    reference_name: str | None = Field(default=None, max_length=300)
    route_estimate_id: str | None = Field(default=None, max_length=80)
    estimated_cost: int = Field(default=0, ge=0)
    opening_time: time | None = None
    closing_time: time | None = None
    closed_dates: list[date] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)


class DayPlanV2(BaseModel):
    """One typed day in a structured trip plan."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    date: date
    day_index: int = Field(..., ge=0, le=29)
    city: str = Field(..., min_length=1, max_length=120)
    is_transfer_day: bool = False
    transfer_info: str = Field(default="", max_length=1000)
    description: str = Field(..., min_length=1, max_length=2000)
    transportation: str = Field(default="public transit", max_length=200)
    accommodation: str = Field(default="", max_length=200)
    hotel: HotelV2 | None = None
    attractions: list[AttractionV2] = Field(default_factory=list)
    meals: list[MealV2] = Field(default_factory=list)
    timeline: list[ScheduleItemV2] = Field(default_factory=list)
    arrangement_rationale: str = Field(default="", max_length=2000)


class WeatherInfoV2(BaseModel):
    """Structured daily weather without free-form numeric fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    date: date
    city: str = Field(..., min_length=1, max_length=120)
    day_weather: str = Field(default="", max_length=120)
    night_weather: str = Field(default="", max_length=120)
    day_temp: int = Field(default=0, ge=-100, le=100)
    night_temp: int = Field(default=0, ge=-100, le=100)
    wind_direction: str = Field(default="", max_length=120)
    wind_power: str = Field(default="", max_length=120)


class RouteEstimateV2(BaseModel):
    """Provider-backed distance estimate between two itinerary locations."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    estimate_id: str = Field(..., min_length=1, max_length=80)
    origin: str = Field(..., min_length=1, max_length=200)
    destination: str = Field(..., min_length=1, max_length=200)
    mode: Literal["driving", "walking", "straight_line"] = "driving"
    distance_meters: int | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=0)
    provider: str = Field(..., min_length=1, max_length=80)
    status: Literal["verified", "estimated", "unavailable"]
    detail: str = Field(default="", max_length=1000)


class IntercityTransportOptionV2(BaseModel):
    """Planning-level transport advice without fabricated service identifiers."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    option_id: str = Field(..., min_length=1, max_length=80)
    leg_index: int = Field(..., ge=0, le=30)
    origin: str = Field(..., min_length=1, max_length=200)
    destination: str = Field(..., min_length=1, max_length=200)
    mode: Literal["train", "flight", "coach", "driving", "public_transit"]
    recommended: bool = False
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    estimated_cost_per_person: int | None = Field(default=None, ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    route_estimate_id: str | None = Field(default=None, max_length=80)
    estimate_status: Literal["verified", "estimated", "unavailable"]
    advice: str = Field(..., min_length=1, max_length=1000)
    caveats: list[str] = Field(default_factory=list)


class BudgetV2(BaseModel):
    """Typed budget fields; deterministic recalculation arrives in Phase 5."""

    model_config = ConfigDict(extra="forbid")

    total_attractions: int = Field(default=0, ge=0)
    total_hotels: int = Field(default=0, ge=0)
    total_meals: int = Field(default=0, ge=0)
    total_transportation: int = Field(default=0, ge=0)
    total_inter_city_transport: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)


class TripPlanV2(BaseModel):
    """Primary structured-output schema for the JourneyGraph planner."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["2.0"] = "2.0"
    origin: str = Field(..., min_length=1, max_length=120)
    city: str = Field(..., min_length=1, max_length=120)
    cities: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date
    days: list[DayPlanV2] = Field(..., min_length=1, max_length=30)
    transport_options: list[IntercityTransportOptionV2] = Field(default_factory=list)
    route_matrix: list[RouteEstimateV2] = Field(default_factory=list)
    weather_info: list[WeatherInfoV2] = Field(default_factory=list)
    overall_suggestions: str = Field(..., min_length=1, max_length=4000)
    budget: BudgetV2 | None = None
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    research_updated_at: datetime | None = None
    research_status: Literal["complete", "partial", "unavailable"] = "unavailable"
    validation_report: ValidationReportV2 = Field(default_factory=ValidationReportV2)
    revision_count: int = Field(default=0, ge=0, le=2)

    @model_validator(mode="after")
    def validate_plan_window(self) -> TripPlanV2:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        expected_days = (self.end_date - self.start_date).days + 1
        if len(self.days) != expected_days:
            raise ValueError("days must cover the inclusive date range")
        if [day.day_index for day in self.days] != list(range(expected_days)):
            raise ValueError("day_index values must be contiguous and zero-based")
        if [day.date for day in self.days] != [
            self.start_date + timedelta(days=offset) for offset in range(expected_days)
        ]:
            raise ValueError("day dates must be contiguous across the requested window")
        return self
