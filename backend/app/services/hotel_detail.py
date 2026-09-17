"""Room evidence with user-approved reference estimates, not verified totals."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ..config import Settings
from ..domain.travel_models import TravelSearchRequest
from .hotel_pricing import amount, estimate_stay
from .travel_search import capabilities, run_readonly_mcp


class RoomEvidence(BaseModel):
    rate_plan_id: str
    room_name: str
    currency: str | None = None
    supplier_average_price: Decimal | None = None
    estimated_stay_total: Decimal | None = None
    max_occupancy: int | None = None
    on_request: bool | None = None


class HotelDetailEvidence(BaseModel):
    hotel_id: int
    check_in: str
    check_out: str
    adults: int
    room_count: Literal[1] = 1
    status: Literal["blocked", "estimated"] = "blocked"
    reason: Literal[
        "disabled",
        "provider_unavailable",
        "response_mismatch",
        "no_eligible_rooms",
        "whole_stay_price_unverified",
        "reference_price_estimate",
    ]
    rooms: list[RoomEvidence] = Field(default_factory=list)
    stay_total: Decimal | None = None
    estimated_stay_total: Decimal | None = None
    selected_rate_plan_id: str | None = None
    currency: str | None = None
    pricing_note: str = "按房型参考均价 × 晚数估算，税费待核实；并非确定总价。"
    taxes: Decimal | None = None
    fetched_at: datetime | None = None
    source_url: str = "https://mcp.rollinggo.cn/mcp"


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
                estimated_stay_total=estimate_stay(row.get("averagePrice"), query.nights),
                max_occupancy=capacity,
                on_request=False,
            )
        )
    result.reason = "whole_stay_price_unverified" if result.rooms else "no_eligible_rooms"
    eligible = [
        room
        for room in result.rooms
        if room.currency == "CNY" and room.estimated_stay_total is not None
    ]
    if eligible:
        selected = min(eligible, key=lambda room: room.estimated_stay_total)
        result.status = "estimated"
        result.reason = "reference_price_estimate"
        result.estimated_stay_total = selected.estimated_stay_total
        result.selected_rate_plan_id = selected.rate_plan_id
        result.currency = selected.currency
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
