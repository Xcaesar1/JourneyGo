"""Observed hotel detail shape must not become an invented whole-stay quote."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from backend.app.config import Settings
from backend.app.domain.travel_models import TravelSearchRequest
from backend.app.services import hotel_detail as service
from backend.app.services import travel_search
from backend.scripts import travel_mcp_bridge


def query(**kwargs):
    return TravelSearchRequest(
        provider="hotel",
        destination="西安",
        date=datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=3),
        nights=4,
        **{"adults": 1, **kwargs},
    )


def fixture(request):
    return {
        "success": True,
        "hotelId": 123,
        "checkIn": request.date.isoformat(),
        "checkOut": (request.date + timedelta(days=4)).isoformat(),
        "roomRatePlans": [
            {
                "ratePlanId": "fixture-room",
                "roomName": "模拟商务房",
                "averagePrice": "350.12",
                "currency": "CNY",
                "isOnRequest": False,
                "roomInfo": {"maxOccupancy": 2},
            }
        ],
    }


def test_four_nights_and_one_room_arguments():
    request = query(adults=2)
    args = service.detail_arguments(request, 123)
    assert args["occupancyParam"] == {
        "adultCount": 2,
        "childCount": 0,
        "childAgeDetails": [],
        "roomCount": 1,
    }
    assert args["dateParam"]["checkOutDate"] == (request.date + timedelta(days=4)).isoformat()
    assert "localeParam" not in args


@pytest.mark.parametrize("adults", [1, 2])
def test_average_price_not_promoted_or_multiplied(adults):
    request = query(adults=adults)
    result = service.inspect_detail(request, 123, fixture(request))
    assert result.status == "blocked" and result.reason == "whole_stay_price_unverified"
    assert result.rooms[0].supplier_average_price == Decimal("350.12")
    assert result.stay_total is None and result.taxes is None
    assert result.fetched_at is not None


@pytest.mark.parametrize("value", [None, "", True, -1, "NaN", "Infinity", {}])
def test_unknown_price_never_becomes_zero(value):
    assert service.amount(value) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("hotelId", 456),
        ("hotelId", True),
        ("checkIn", "2020-01-01"),
        ("checkOut", "2020-01-01"),
        ("roomRatePlans", {}),
    ],
)
def test_mismatched_response_rejected(field, value):
    request = query()
    payload = {**fixture(request), field: value}
    result = service.inspect_detail(request, 123, payload)
    assert result.reason == "response_mismatch" and not result.rooms


@pytest.mark.parametrize(
    "patch",
    [
        {"isOnRequest": True},
        {"isOnRequest": None},
        {"roomInfo": {}},
        {"roomInfo": {"maxOccupancy": 1}},
        {"ratePlanId": ""},
    ],
)
def test_ineligible_or_uncertain_rooms_rejected(patch):
    request = query(adults=2)
    payload = fixture(request)
    payload["roomRatePlans"][0].update(patch)
    assert service.inspect_detail(request, 123, payload).reason == "no_eligible_rooms"


def test_unverified_total_field_is_not_silently_enabled():
    request = query()
    payload = fixture(request)
    payload["roomRatePlans"][0]["totalPrice"] = 1400
    assert service.inspect_detail(request, 123, payload).stay_total is None


def test_disabled_service_never_calls_provider(monkeypatch):
    monkeypatch.setattr(service, "run_readonly_mcp", lambda *a, **k: pytest.fail("network"))
    settings = Settings(_env_file=None, travel_hotel_enabled=False)
    result = service.fetch_detail(query(), 123, settings)
    assert result.reason == "disabled" and result.fetched_at is None
    with pytest.raises(ValueError, match="disabled"):
        service.fetch_search_tags(settings)


def test_provider_timeout_is_not_retried_or_leaked(monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise TimeoutError("private-provider-error")

    monkeypatch.setattr(service, "run_readonly_mcp", fail)
    settings = Settings(
        _env_file=None,
        demo_mode=False,
        travel_hotel_enabled=True,
        rollinggo_api_key="fake-test-key",
    )
    result = service.fetch_detail(query(), 123, settings)
    assert len(calls) == 1 and result.reason == "provider_unavailable"
    assert "private" not in result.model_dump_json()


@pytest.mark.parametrize(
    "tool",
    [
        "hotelPriceConfirm",
        "createHotelBookingWithPaymentURL",
        "searchHotelOrders",
        "getFlightPriceByCities",
    ],
)
def test_non_readonly_or_cross_provider_tool_rejected_before_subprocess(monkeypatch, tool):
    monkeypatch.setattr(travel_search.subprocess, "run", lambda *a, **k: pytest.fail("process"))
    with pytest.raises(ValueError, match="unsupported"):
        travel_search.run_readonly_mcp("hotel", {}, Settings(_env_file=None), tool=tool)


@pytest.mark.parametrize("tool", ["searchHotels", "getHotelDetail", "getHotelSearchTags"])
def test_readonly_tools_use_hotel_secret_only(monkeypatch, tool):
    def run(*args, **kwargs):
        assert json.loads(kwargs["input"])["tool"] == tool
        assert kwargs["env"]["ROLLINGGO_API_KEY"] == "fake-hotel-key"
        assert "VARIFLIGHT_API_KEY" not in kwargs["env"]
        return SimpleNamespace(stdout='{"success":true}')

    monkeypatch.setattr(travel_search.subprocess, "run", run)
    settings = Settings(_env_file=None, rollinggo_api_key="fake-hotel-key")
    assert travel_search.run_readonly_mcp("hotel", {}, settings, tool=tool)["success"]


@pytest.mark.parametrize(
    "payload",
    [
        {"provider": "hotel", "tool": "hotelPriceConfirm"},
        {"provider": "hotel", "tool": "createHotelBookingWithPaymentURL"},
        {"provider": "hotel", "tool": "searchHotelOrders"},
        {"provider": "train", "tool": "getHotelDetail"},
        {"provider": "hotel", "tool": []},
        {"provider": "unknown"},
    ],
)
async def test_bridge_checks_allowlist_before_connecting(monkeypatch, payload):
    monkeypatch.setattr(
        travel_mcp_bridge, "streamablehttp_client", lambda *a, **k: pytest.fail("network")
    )
    with pytest.raises(ValueError):
        await travel_mcp_bridge.query(payload)


@pytest.mark.parametrize("tool", ["searchHotels", "getHotelDetail", "getHotelSearchTags"])
def test_bridge_readonly_tools(tool):
    assert travel_mcp_bridge.resolve_tool({"provider": "hotel", "tool": tool}) == tool
    assert travel_mcp_bridge.resolve_tool({"provider": "hotel"}) == "searchHotels"
