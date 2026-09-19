"""Travel query isolation, normalization, API consent, cache and cost boundaries."""

import json
import subprocess
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from backend.app.api.v2 import travel
from backend.app.config import Settings
from backend.app.domain.travel_models import TravelSearchRequest
from backend.app.services import travel_search as service
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError


def query(provider="train", **overrides):
    return TravelSearchRequest.model_validate(
        {
            "provider": provider,
            "origin": "BJS" if provider == "flight" else "北京",
            "destination": "SHA" if provider == "flight" else "西安",
            "date": (
                datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
            ).isoformat(),
            "confirm_paid": provider == "flight",
            **overrides,
        }
    )


def config(**overrides):
    return Settings(
        _env_file=None,
        **{
            "demo_mode": False,
            "api_rate_limit_enabled": False,
            "api_access_code_required": False,
            "api_access_code": "fake-access-code",
            "travel_train_enabled": True,
            "travel_hotel_enabled": True,
            "travel_flight_enabled": True,
            "rollinggo_api_key": "fake-hotel-key",
            "variflight_api_key": "fake-flight-key",
            "travel_flight_call_limit": 1,
            **overrides,
        },
    )


class Store:
    def __init__(self):
        self.data = {}
        self.reservations = 0

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    def eval(self, script, count, key, maximum):
        assert script == service.RESERVE and count == 1
        assert key.startswith("journeygo:travel:flight:calls:")
        if self.reservations >= maximum:
            return 0
        self.reservations += 1
        return 1


def train_payload(request):
    return [
        {
            "start_date": request.date.isoformat(),
            "arrive_date": request.date.isoformat(),
            "start_train_code": "G123",
            "from_station": "北京西",
            "to_station": "西安北",
            "start_time": "07:00",
            "arrive_time": "12:00",
            "prices": [{"seat_name": "二等座", "short": "ze", "num": "有", "price": 522}],
        }
    ]


def flight_payload(request):
    return {
        "code": 200,
        "data": [
            {
                "flightno": "TEST123",
                "depdate": request.date.isoformat(),
                "depcitycode": request.origin,
                "arrcitycode": request.destination,
                "depaptcname": "北京首都",
                "flightdepcode": "PEK",
                "arraptcname": "上海虹桥",
                "flightarrcode": "SHA",
                "flightdeptimeplandate": 1789637400,
                "flightarrtimeplandate": 1789645500,
                "oilfee": "",
                "tax": "",
                "cabins": [
                    {"cabincode": "Y", "classname": "经济舱", "price": 350, "seatnum": 1},
                    {"cabincode": "C", "classname": "公务舱", "price": 200, "seatnum": 0},
                ],
            }
        ],
    }


def test_train_values_are_provider_facts():
    request = query()
    offers = service.normalize(request, train_payload(request))
    assert offers[0].price == 522 and offers[0].availability == "有"
    assert offers[0].price_basis == "per_person"
    assert "北京西" in offers[0].subtitle
    assert service.arguments(request)["format"] == "json"


def test_hotel_first_night_reference_is_estimated_once_per_room():
    request = query("hotel", nights=2, adults=2)
    payload = {
        "success": True,
        "hotelInformationList": [
            {
                "hotelId": 1,
                "name": "测试酒店",
                "description": "<script>untrusted</script>",
                "bookingUrl": "javascript:alert(1)",
                "price": {"hasPrice": True, "lowestPrice": 600, "currency": "CNY"},
            },
            {"hotelId": 2, "name": "无报价", "price": {"hasPrice": False, "lowestPrice": 0}},
        ],
    }
    offers = service.normalize(request, payload)
    assert offers[0].price == 600 and offers[0].price_basis == "first_night_reference"
    assert offers[0].estimated_stay_total == 1200
    assert "2 晚" in offers[0].fare_label
    assert offers[1].price is None
    assert offers[1].estimated_stay_total is None
    assert not offers[0].booking_url
    assert "<script>" not in offers[0].model_dump_json()
    assert service.arguments(request)["place"] == "西安 中国"


def test_flight_prices_exclude_sold_out_and_do_not_invent_taxes():
    request = query("flight")
    offers = service.normalize(request, flight_payload(request))
    assert offers[0].price == 350
    assert "非含税总价" in offers[0].notes[0]
    assert "北京时间" in offers[0].notes[1]
    assert offers[0].departure == "2026-09-17 17:30"


@pytest.mark.parametrize("value", [None, "", "NaN", float("inf"), -1, {}, True])
def test_unknown_money_is_not_zero(value):
    assert service.money(value) is None


def test_zero_money_is_preserved():
    assert service.money(0) == 0


def test_wrong_flight_city_or_date_never_displayed():
    request = query("flight")
    payload = flight_payload(request)
    payload["data"][0]["depcitycode"] = "CAN"
    assert service.normalize(request, payload) == []


@pytest.mark.parametrize(
    "provider,payload",
    [("train", {"error": "failed"}), ("hotel", {"success": False}), ("flight", {"code": 429})],
)
def test_provider_errors_not_mistaken_for_empty(provider, payload):
    with pytest.raises(ValueError):
        service.normalize(query(provider), payload)


@pytest.mark.parametrize(
    "provider,overrides",
    [
        ("train", {"origin": "西安"}),
        ("train", {"date": "2020-01-01"}),
        ("flight", {"origin": "北京"}),
        ("flight", {"origin": "bjs"}),
        ("hotel", {"nights": 29}),
        ("hotel", {"adults": 0}),
        ("hotel", {"country": " "}),
        ("hotel", {"tool": "createOrder"}),
    ],
)
def test_invalid_queries_rejected(provider, overrides):
    with pytest.raises(ValidationError):
        query(provider, **overrides)


def test_train_sale_window():
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    query(date=(today + timedelta(days=14)).isoformat())
    with pytest.raises(ValidationError):
        query(date=(today + timedelta(days=15)).isoformat())


def test_cache_prevents_duplicate_provider_call(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service,
        "run_mcp",
        lambda request, settings: calls.append(request) or train_payload(request),
    )
    store = Store()
    first = service.search(query(), config(), store)
    second = service.search(query(), config(), store)
    assert first.status == "ok" and not first.cached
    assert second.cached and second.fetched_at == first.fetched_at
    assert len(calls) == 1


def test_paid_cache_does_not_spend_twice_and_global_cap_blocks_new_query(monkeypatch):
    monkeypatch.setattr(service, "run_mcp", lambda request, settings: flight_payload(request))
    store = Store()
    assert service.search(query("flight"), config(), store).status == "ok"
    assert service.search(query("flight"), config(), store).cached
    assert (
        service.search(query("flight", destination="CAN"), config(), store).status
        == "budget_exhausted"
    )
    assert store.reservations == 1


def test_failure_is_counted_and_not_retried(monkeypatch):
    calls = []

    def fail(*args):
        calls.append(1)
        raise TimeoutError("fake-secret-must-not-leak")

    monkeypatch.setattr(service, "run_mcp", fail)
    store = Store()
    failed = service.search(query("flight"), config(), store)
    assert failed.status == "unavailable" and "fake-secret" not in failed.model_dump_json()
    assert service.search(query("flight"), config(), store).status == "busy"
    assert (
        service.search(query("flight", destination="CAN"), config(), store).status
        == "budget_exhausted"
    )
    assert len(calls) == 1


def test_redis_failure_fails_closed(monkeypatch):
    class BrokenStore(Store):
        def get(self, key):
            raise OSError("unavailable")

    monkeypatch.setattr(service, "run_mcp", lambda *args: pytest.fail("network forbidden"))
    assert service.search(query("flight"), config(), BrokenStore()).status == "unavailable"


@pytest.mark.parametrize(
    "overrides",
    [
        {"demo_mode": True},
        {"travel_flight_enabled": False},
        {"variflight_api_key": ""},
        {"api_access_code": ""},
        {"travel_flight_call_limit": 0},
    ],
)
def test_disabled_modes_never_call_network(monkeypatch, overrides):
    monkeypatch.setattr(service, "run_mcp", lambda *args: pytest.fail("network forbidden"))
    assert service.search(query("flight"), config(**overrides), Store()).status == "disabled"


def test_service_requires_paid_consent(monkeypatch):
    monkeypatch.setattr(service, "run_mcp", lambda *args: pytest.fail("network forbidden"))
    assert (
        service.search(query("flight", confirm_paid=False), config(), Store()).status == "disabled"
    )


def test_subprocess_only_receives_provider_secret_and_allowlisted_tool(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-unrelated-secret")

    def run(args, **kwargs):
        assert "OPENAI_API_KEY" not in kwargs["env"]
        assert "ROLLINGGO_API_KEY" not in kwargs["env"]
        assert kwargs["env"]["VARIFLIGHT_API_KEY"] == "fake-flight-key"
        assert "fake-flight-key" not in str(args)
        body = json.loads(kwargs["input"])
        assert body["provider"] == "flight" and "tool" not in body
        return SimpleNamespace(stdout='{"echo":"fake-flight-key"}')

    monkeypatch.setattr(subprocess, "run", run)
    assert service.run_mcp(query("flight"), config()) == {"echo": "[redacted]"}


def test_api_paid_auth_consent_and_no_secrets(monkeypatch):
    settings = config()
    monkeypatch.setattr(travel, "get_settings", lambda: settings)
    calls = []
    monkeypatch.setattr(
        travel,
        "search",
        lambda payload, settings: (
            calls.append(payload) or service.response(payload, "empty", "No results")
        ),
    )
    app = FastAPI()
    app.include_router(travel.router, prefix="/api/v2")
    with TestClient(app) as client:
        body = query("flight").model_dump(mode="json")
        assert client.post("/api/v2/travel/search", json=body).status_code == 401
        headers = {"X-Access-Code": "fake-access-code"}
        assert (
            client.post(
                "/api/v2/travel/search", json={**body, "confirm_paid": False}, headers=headers
            ).status_code
            == 422
        )
        assert client.post("/api/v2/travel/search", json=body, headers=headers).status_code == 200
        assert len(calls) == 1
        public = client.get("/api/v2/travel/capabilities")
        assert "fake-" not in public.text
        flight = public.json()["flight"]
        assert flight["enabled"] is True and flight["paid"] is True
        assert flight["city_codes"]["深圳"] == "SZX"
        assert flight["city_codes"]["武汉"] == "WUH"
        assert len(flight["city_codes"]) >= 250


def test_provider_empty_has_timestamp(monkeypatch):
    monkeypatch.setattr(service, "run_mcp", lambda *args: [])
    result = service.search(query(), config(), Store())
    assert result.status == "empty" and result.fetched_at and not result.offers
