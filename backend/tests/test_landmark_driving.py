from datetime import datetime

import httpx
import pytest
from backend.app.agents.journey_graph.nodes.validate import _validate_routes
from backend.app.domain.landmarks import LANDMARKS
from backend.app.services.landmark_transit import choose_driving, choose_transit, query_driving
from backend.app.services.travel_ledger import PlanningInputRequired
from backend.tests.test_landmark_planning import landmark_planner, transit


def driving(_args, duration="2400"):
    return {"status": "1", "route": {"paths": [{"duration": duration, "distance": "35000", "tolls": "100", "taxi_cost": "200"}]}}


@pytest.mark.parametrize("distance,car_duration,expected,calls_expected", [
    (9999, "600", "public_transit", 0),
    (10000, "600", "driving", 1),
    (10001, "600", "driving", 1),
    (10001, "1800", "public_transit", 1),
    (10001, "3600", "public_transit", 1),
])
def test_ten_km_threshold_compares_total_time_and_keeps_public_transit(distance, car_duration, expected, calls_expected):
    p, _ = landmark_planner(LANDMARKS[1])
    payload = transit({})
    payload["route"]["transits"][0].update(distance=str(distance), duration="2700")
    payload["route"]["transits"][0]["segments"][0]["bus"]["buslines"] = [{"name": "地铁1号线", "type": "地铁线路"}]
    calls = []
    p.transit = lambda _: payload
    p.driving = lambda args: (calls.append(args), driving(args, car_duration))[1]
    left = {"name": "酒店", "location": {"longitude": 100.1, "latitude": 26.8}}
    right = {"name": "景点", "location": {"longitude": 100.11, "latitude": 26.81}}
    result = p.landmark_route(left, right, datetime(2026, 9, 21, 9))
    assert result["mode"] == expected
    assert len(calls) == calls_expected
    if expected == "driving":
        assert "达到10公里" in result["note"]
    else:
        assert result["lines"] == ["地铁1号线"]


def test_distant_transit_remains_available_when_driving_has_no_result():
    p, _ = landmark_planner(LANDMARKS[1])
    payload = transit({})
    payload["route"]["transits"][0]["distance"] = "12000"
    p.transit = lambda _: payload
    place = {"location": {"longitude": 100, "latitude": 27}}
    assert p.landmark_route(place, place, datetime(2026, 9, 21, 9))["mode"] == "public_transit"


@pytest.mark.parametrize("distance", [None, "", "NaN", "inf", "-1"])
def test_missing_transit_distance_does_not_discard_metro(distance):
    payload = transit({})
    payload["route"]["transits"][0]["distance"] = distance
    assert choose_transit(payload)["distance_meters"] is None


def test_return_only_fallback_preserves_bus_and_excludes_costs():
    p, _ = landmark_planner(LANDMARKS[1])
    calls = []
    p.transit = lambda args: transit(args) if args["time"] == "09:00" else {"status": "1", "route": {"transits": []}}

    def drive(args):
        calls.append(args)
        return driving(args)

    p.driving = drive
    plan = p.run()
    assert len(calls) == 1
    bus = [r for r in plan.route_matrix if r.provider == "amap-transit"]
    car = [r for r in plan.route_matrix if r.provider == "amap-driving"]
    assert len(bus) == len(car) == 1
    assert car[0].mode == "driving" and car[0].duration_minutes == 70
    assert car[0].distance_meters == 35000
    assert car[0].origin == "玉龙雪山" and car[0].destination == "测试商务酒店"
    assert "非已预约车辆" in car[0].detail
    summary = plan.travel_summary
    assert len(summary["driving_fallback_days"]) == 1
    day = next(d for d in plan.days if d.date.isoformat() in summary["driving_fallback_days"])
    assert day.attractions[0].visit_duration == 360
    assert "费用未评估" in day.transportation
    assert any("驾车返回酒店" in t.title for t in day.timeline)
    assert all(a.end == b.start for a, b in zip(day.timeline, day.timeline[1:]))
    assert "driving_transfers" in summary["excluded_costs"]
    item = next(i for i in summary["cost_items"] if i["category"] == "driving_transfers")
    assert item["status"] == "unknown" and item["amount_cents"] is None
    local = next(i for i in summary["cost_items"] if i["category"] == "local_transport")
    assert local["amount_cents"] == 4 * 3000 * p.request.travelers
    assert summary["expected_cents"] == sum(i["amount_cents"] or 0 for i in summary["cost_items"])
    assert any("不能据此认定整趟费用在预算内" in n for n in summary["planning_notices"])
    assert not any(i.severity == "critical" for i in _validate_routes({"request": p.request}, plan))


def test_bus_success_never_calls_driving():
    p, _ = landmark_planner(LANDMARKS[1])
    p.driving = lambda _: pytest.fail("Bus evidence exists; no driving query expected")
    plan = p.run()
    assert not plan.travel_summary["driving_fallback_days"]
    assert "driving_transfers" not in plan.travel_summary["excluded_costs"]


def test_two_driving_legs_are_independent_and_long_dedicated_day_validates():
    p, _ = landmark_planner(LANDMARKS[3])
    search = p.maps

    def distinct_locations(city, keyword, kind):
        result = search(city, keyword, kind)
        if kind == "110000":
            result["pois"] = [{**place, "location": "108.96,34.27"} for place in result["pois"]]
        return result

    p.maps = distinct_locations
    p.transit = lambda _: {"status": "1", "route": {"transits": []}}
    calls = []

    def drive(args):
        calls.append(args)
        return driving(args, "4800")

    p.driving = drive
    plan = p.run()
    routes = [r for r in plan.route_matrix if r.provider == "amap-driving"]
    assert len(calls) == len(routes) == 2
    assert calls[0]["origin"] == calls[1]["destination"]
    assert calls[0]["destination"] == calls[1]["origin"]
    assert not any(i.code == "daily_commute_excessive" for i in _validate_routes({"request": p.request}, plan))
    routes[1].provider = "local-estimate"
    assert any(i.code == "daily_commute_excessive" for i in _validate_routes({"request": p.request}, plan))


def test_driving_does_not_shrink_visit_to_fit():
    p, _ = landmark_planner(LANDMARKS[1])
    p.transit = lambda _: {"status": "1", "route": {"transits": []}}
    p.driving = lambda args: driving(args, "18000")
    with pytest.raises(PlanningInputRequired, match="往返接驳、游览"):
        p.run()


@pytest.mark.parametrize("payload", [None, {}, {"status": "0"}, {"status": "1", "route": None}, {"status": "1", "route": {"paths": []}}])
def test_no_driving_evidence(payload):
    assert choose_driving(payload) is None


@pytest.mark.parametrize("duration", [None, "", "NaN", "inf", "0", "-1", "43200"])
def test_invalid_driving_duration(duration):
    assert choose_driving(driving({}, duration)) is None


def test_driving_api_uses_coordinates_not_quote_or_future_departure(monkeypatch):
    client_class = httpx.Client

    def handler(req):
        assert req.url.path == "/v3/direction/driving"
        assert req.url.params["origin"] == "100.1,26.1"
        assert req.url.params["destination"] == "100.2,27.1"
        assert "date" not in req.url.params
        return httpx.Response(200, json=driving({}))

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs))
    result = choose_driving(query_driving("test-only", {"origin": "100.1,26.1", "destination": "100.2,27.1"}))
    assert result["minutes"] == 70
    assert not any(key in result for key in ["cost", "tolls", "taxi_cost"])
