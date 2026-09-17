"""Weather isolation, identity matching and deterministic output contracts."""

import io
import json
import subprocess
from datetime import date
from types import SimpleNamespace

import pytest
from backend.app.agents.journey_graph import build_journey_graph
from backend.app.config import Settings
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE, TripRequestV2
from backend.app.services import weather


def district(monkeypatch, items):
    monkeypatch.setattr(
        weather,
        "urlopen",
        lambda *a, **kw: io.StringIO(json.dumps({"status": "1", "districts": items})),
    )


def test_xian_requires_exact_administrative_city(monkeypatch):
    district(monkeypatch, [{"name": "西安村", "level": "district", "center": "119.54,27.01"}])
    assert weather.resolve_city("西安", "fake-test-key") is None
    district(monkeypatch, [{"name": "西安市", "level": "city", "center": "108.94,34.26"}])
    lon, lat = weather.resolve_city("西安", "fake-test-key")
    assert 108.93 < lon < 108.94
    assert 34.26 < lat < 34.27


def test_ambiguous_and_missing_key_are_unavailable(monkeypatch):
    item = {"name": "西安市", "level": "city", "center": "108.94,34.26"}
    district(monkeypatch, [item, item])
    assert weather.resolve_city("西安", "fake-test-key") is None
    assert weather.resolve_city("西安", "") is None


def test_conversion_outside_china_unchanged():
    assert weather.gcj02_to_wgs84(-73.98, 40.75) == (-73.98, 40.75)
    lon, lat = weather.gcj02_to_wgs84(116.404, 39.915)
    assert lon == pytest.approx(116.397756, abs=0.00001)
    assert lat == pytest.approx(39.913596, abs=0.00001)


def test_real_fields_dates_and_coordinate_only_call(monkeypatch):
    monkeypatch.setattr(weather, "resolve_city", lambda *a: (108.94, 34.26))

    def run(args, **kwargs):
        assert json.loads(kwargs["input"])["location"] == "34.26,108.94"
        assert "OPENAI_API_KEY" not in kwargs["env"]
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "forecast": [
                        {
                            "date": "2026-09-16",
                            "temp_max_c": 23.4,
                            "temp_min_c": 18.1,
                            "precipitation_prob_pct": 0,
                            "condition": "Overcast",
                        },
                        {"date": "2026-09-17", "temp_max_c": None, "temp_min_c": 17},
                        {"date": "2026-09-18", "temp_max_c": 25, "temp_min_c": 18},
                    ]
                }
            )
        )

    monkeypatch.setattr(weather.subprocess, "run", run)
    rows, status = weather.WeatherProvider("python", "fake-test-key").collect(
        "西安", date(2026, 9, 16), date(2026, 9, 17)
    )
    assert status == "partial_or_out_of_range"
    assert len(rows) == 1 and rows[0]["precipitation_probability"] == 0
    assert rows[0]["humidity"] is None
    assert rows[0]["fetched_at"] and rows[0]["source_url"]


@pytest.mark.parametrize(
    "error", [TimeoutError(), ValueError(), subprocess.TimeoutExpired("python", 30)]
)
def test_failure_degrades_without_raising(monkeypatch, error):
    def fail(*a):
        raise error

    monkeypatch.setattr(weather, "resolve_city", fail)
    assert weather.WeatherProvider("python", "fake-test-key").collect(
        "西安", date(2026, 9, 16), date(2026, 9, 17)
    ) == ([], "weather_unavailable")


def test_demo_never_calls_weather(monkeypatch):
    monkeypatch.setattr(weather, "resolve_city", lambda *a: pytest.fail("network forbidden"))
    request = TripRequestV2.model_validate(TRIP_REQUEST_V2_EXAMPLE)
    assert weather.collect_weather(request, Settings(demo_mode=True, weather_enabled=True)) == (
        {},
        {},
    )


def test_graph_preserves_provider_weather_not_model_weather(monkeypatch):
    request = TripRequestV2.model_validate(TRIP_REQUEST_V2_EXAMPLE)
    row = {
        "city": "Tokyo",
        "date": "2026-10-10",
        "day_temp": 23,
        "night_temp": 17,
        "precipitation_probability": 8,
        "source_url": "https://open-meteo.com/",
    }
    monkeypatch.setattr(weather, "collect_weather", lambda *a: ({"Tokyo": [row]}, {}))
    result = build_journey_graph(weather_settings=Settings()).invoke(
        {"request": request, "trip_id": "weather-test", "task_id": "weather-test"}
    )
    plan = result["final_plan"]
    assert len(plan.weather_info) == 1
    assert plan.weather_info[0].precipitation_probability == 8


def test_multiple_destinations_use_their_own_inclusive_travel_dates(monkeypatch):
    request = TripRequestV2.model_validate(TRIP_REQUEST_V2_EXAMPLE)
    calls = []
    def collect(self, city, start, end):
        calls.append((city, start, end))
        return [], "partial_or_out_of_range"
    monkeypatch.setattr(weather.WeatherProvider, "collect", collect)
    weather.collect_weather(request, Settings(weather_enabled=True, demo_mode=False))
    from datetime import timedelta
    start = request.start_date
    for call, destination in zip(calls, request.destinations, strict=True):
        end = start + timedelta(days=destination.days - 1)
        assert call == (destination.city, start, end)
        start = end + timedelta(days=1)
    assert start == request.end_date + timedelta(days=1)
