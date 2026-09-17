"""Read-only RollingGo room evidence; never promote an ambiguous price to a quote.

The observed CN endpoint exposes averagePrice without a documented billing basis.
This adapter deliberately cannot return a verified stay quote until that contract
is established. It is not wired into the existing estimated itinerary workflow.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field

from ..config import Settings
from ..domain.travel_models import TravelSearchRequest
from .travel_search import capabilities, run_readonly_mcp


class RoomEvidence(BaseModel):
    rate_plan_id: str
    room_name: str
    currency: str | None = None
    supplier_average_price: Decimal | None = None
    max_occupancy: int | None = None
    on_request: bool | None = None


class HotelDetailEvidence(BaseModel):
    hotel_id: int
    check_in: str
    check_out: str
    adults: int
    room_count: Literal[1] = 1
    status: Literal["blocked"] = "blocked"
    reason: Literal[
        "disabled",
        "provider_unavailable",
        "response_mismatch",
        "no_eligible_rooms",
        "whole_stay_price_unverified",
    ]
    rooms: list[RoomEvidence] = Field(default_factory=list)
    stay_total: Decimal | None = None
    taxes: Decimal | None = None
    fetched_at: datetime | None = None
    source_url: str = "https://mcp.rollinggo.cn/mcp"


def amount(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def detail_arguments(query: TravelSearchRequest, hotel_id: int) -> dict:
    if query.provider != "hotel" or query.adults > 2:
        raise ValueError("Hotel detail supports one room for one or two adults.")
    if isinstance(hotel_id, bool) or not isinstance(hotel_id, int) or hotel_id <= 0:
        raise ValueError("A valid hotel ID from searchHotels is required.")
    return {
        "hotelId": hotel_id,
        "dateParam": {
            "checkInDate": query.date.isoformat(),
            "checkOutDate": (query.date + timedelta(days=query.nights)).isoformat(),
        },
        "occupancyParam": {
            "adultCount": query.adults,
            "childCount": 0,
            "childAgeDetails": [],
            "roomCount": 1,
        },
    }


def inspect_detail(query: TravelSearchRequest, hotel_id: int, payload) -> HotelDetailEvidence:
    args = detail_arguments(query, hotel_id)
    result = HotelDetailEvidence(
        hotel_id=hotel_id,
        check_in=args["dateParam"]["checkInDate"],
        check_out=args["dateParam"]["checkOutDate"],
        adults=query.adults,
        reason="response_mismatch",
        fetched_at=datetime.now(timezone.utc),
    )
    if not isinstance(payload, dict) or payload.get("success") is not True:
        result.reason = "provider_unavailable"
        return result
    if (
        type(payload.get("hotelId")) is not int
        or payload["hotelId"] != hotel_id
        or payload.get("checkIn") != result.check_in
        or payload.get("checkOut") != result.check_out
        or not isinstance(payload.get("roomRatePlans"), list)
    ):
        return result
    for row in payload["roomRatePlans"]:
        if not isinstance(row, dict):
            continue
        info = row.get("roomInfo")
        capacity = info.get("maxOccupancy") if isinstance(info, dict) else None
        if type(capacity) is not int or capacity < query.adults:
            continue
        if row.get("isOnRequest") is not False:
            continue
        if not all(
            isinstance(row.get(k), str) and row[k].strip() for k in ("ratePlanId", "roomName")
        ):
            continue
        result.rooms.append(
            RoomEvidence(
                rate_plan_id=row["ratePlanId"][:500],
                room_name=row["roomName"][:200],
                currency=row.get("currency") if isinstance(row.get("currency"), str) else None,
                supplier_average_price=amount(row.get("averagePrice")),
                max_occupancy=capacity,
                on_request=False,
            )
        )
    result.reason = "whole_stay_price_unverified" if result.rooms else "no_eligible_rooms"
    return result


def fetch_detail(query: TravelSearchRequest, hotel_id: int, settings: Settings):
    args = detail_arguments(query, hotel_id)
    if not capabilities(settings)["hotel"]["enabled"]:
        result = inspect_detail(query, hotel_id, None)
        result.reason = "disabled"
        result.fetched_at = None
        return result
    try:
        payload = run_readonly_mcp("hotel", args, settings, tool="getHotelDetail")
    except Exception:
        result = inspect_detail(query, hotel_id, None)
        result.fetched_at = None
        return result
    return inspect_detail(query, hotel_id, payload)


def fetch_search_tags(settings: Settings):
    if not capabilities(settings)["hotel"]["enabled"]:
        raise ValueError("hotel_service_disabled")
    return run_readonly_mcp("hotel", {}, settings, tool="getHotelSearchTags")
