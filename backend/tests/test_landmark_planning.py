from datetime import datetime

import httpx
import pytest
from backend.app.domain.landmarks import LANDMARKS, discovery_queries, metadata, same_experience
from backend.app.domain.trip_models import CityStayV2
from backend.app.services.attraction_discovery import (
    AmapAttractionDiscoveryProvider,
    rank_amap_pois,
)
from backend.app.services.landmark_transit import choose_transit
from backend.app.services.travel_ledger import PlanningInputRequired
from backend.tests.test_one_click_travel import maps, planner, request


def transit(_args):
    return {
        "status": "1",
        "route": {
            "transits": [
                {
                    "duration": "1800",
                    "walking_distance": "200",
                    "segments": [{"bus": {"buslines": [{"name": "测试公交"}]}}],
                }
            ]
        },
    }


def poi(name, index, location="108.95,34.26"):
    return {
        "id": f"BLAND{index}",
        "name": name,
        "address": "测试地点",
        "adcode": "610100",
        "location": location,
        "type": "风景名胜",
    }


def landmark_planner(item, **changes):
    r = request().model_copy(
        update={
            "origin": "杭州",
            "destinations": [CityStayV2(city=item["city"], days=5)],
            "excluded_attractions": [
                other["name"]
                for other in LANDMARKS
                if other["city"] == item["city"] and other != item
            ],
            **changes,
        }
    )
    queries = []

    def search(city, keyword, kind):
        queries.append(keyword)
        if kind != "110000":
            return maps(city, keyword, kind)
        # A full first generic page must not prevent the later exact landmark search.
        rows = [poi(f"普通景点{i}", i) for i in range(25)]
        if keyword == item["name"]:
            rows = [poi(item["name"], 99)]
        if item["city"] == "大同" and keyword == "景点":
            rows += [
                poi(name, 200 + i)
                for i, name in enumerate(
                    ["大同古城", "大同古城墙", "大同古城南城墙", "华严寺", "善化寺"]
                )
            ]
        return {"status": "1", "pois": rows}

    return planner(r, maps=search, transit=transit), queries


@pytest.mark.parametrize("item", LANDMARKS, ids=[item["group"] for item in LANDMARKS])
def test_seven_landmarks_are_recalled_prioritized_and_scheduled(item):
    p, queries = landmark_planner(item)
    plan = p.run()
    selected = [
        sight for day in plan.days for sight in day.attractions if sight.name == item["name"]
    ]
    assert len(selected) == 1
    assert selected[0].visit_duration == item["minutes"]
    assert item["name"] in queries
    assert set(discovery_queries(item["city"])) <= set(queries)
    if item["style"] != "standard":
        day = next(day for day in plan.days if selected[0] in day.attractions)
        assert day.day_index in {1, 2, 3}
        assert len(day.attractions) == 1
        assert any(route.mode == "public_transit" for route in plan.route_matrix)
    assert all(
        a.end == b.start for day in plan.days for a, b in zip(day.timeline, day.timeline[1:])
    )


def test_datong_wall_group_preserves_independent_temples():
    names = ["大同古城", "大同古城墙", "大同古城南城墙", "华严寺", "善化寺"]
    ranked = rank_amap_pois(
        {"status": "1", "pois": [poi(name, i) for i, name in enumerate(names)]}, "大同"
    )
    assert {item.name for item in ranked} == {"大同古城墙", "华严寺", "善化寺"}
    assert not same_experience("大同", "大同古城", "华严寺")


def test_explicit_duplicate_must_visits_pause_before_queries():
    p, queries = landmark_planner(LANDMARKS[3], must_visit=["大同古城墙", "大同古城南城墙"])
    with pytest.raises(PlanningInputRequired, match="同一游览体验") as caught:
        p.discover_attractions("大同")
    assert caught.value.payload["code"] == "duplicate_must_visit"
    assert not queries


def test_exclusion_applies_to_landmark_aliases_and_survives_scheduling():
    p, _ = landmark_planner(LANDMARKS[3], excluded_attractions=["云冈石窟景区", "大同古城南城墙"])
    plan = p.run()
    assert not any(
        metadata("大同", sight.name).get("experience_group")
        in {"datong-yungang", "datong-city-wall"}
        for day in plan.days
        for sight in day.attractions
    )


def test_missing_public_transit_does_not_become_driving_or_silent_omission():
    p, _ = landmark_planner(LANDMARKS[3])
    p.transit = lambda args: {"status": "1", "route": {"transits": []}}
    with pytest.raises(PlanningInputRequired) as caught:
        p.run()
    assert caught.value.payload["code"] == "landmark_unplaced"
    assert "公交" in caught.value.payload["message"]
    assert caught.value.payload["diagnostics"]["places"] == ["云冈石窟"]


def test_full_day_landmark_does_not_shrink_to_fit_short_window():
    p, _ = landmark_planner(LANDMARKS[1], daily_end_time=datetime.strptime("14:00", "%H:%M").time())
    with pytest.raises(PlanningInputRequired) as caught:
        p.run()
    assert caught.value.payload["code"] == "landmark_unplaced"


def test_transit_rejects_taxi_and_excess_walking():
    payload = transit({})
    assert choose_transit(payload)["minutes"] == 45
    assert choose_transit(payload, 0) is None
    payload["route"]["transits"][0]["segments"][0]["taxi"] = {"duration": "600"}
    assert choose_transit(payload) is None


def test_non_landmark_keeps_legacy_default_duration():
    plan = planner().run()
    assert all(sight.visit_duration == 90 for day in plan.days for sight in day.attractions)


@pytest.mark.parametrize("item", LANDMARKS, ids=[item["group"] for item in LANDMARKS])
def test_homepage_landmarks_survive_full_generic_pages(item):
    calls = []

    def handler(request):
        keyword = request.url.params["keywords"]
        calls.append(keyword)
        rows = [poi(f"普通公园{i}", i) for i in range(25)]
        if keyword == item["name"]:
            rows = [poi(item["name"], 99)]
        return httpx.Response(200, json={"status": "1", "pois": rows})

    provider = AmapAttractionDiscoveryProvider(
        "fake", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    page = provider.discover(item["city"], interests=["nature"], limit=8)
    assert page.items[0].name == item["name"]
    assert page.items[0].poi_id in page.default_selected_ids
    assert page.items[0].duration_basis == "planning_estimate"
    assert set(discovery_queries(item["city"], ["nature"])) <= set(calls)


def test_missing_landmark_identity_requires_explicit_recovery():
    p, _ = landmark_planner(LANDMARKS[3])
    p.maps = maps
    with pytest.raises(PlanningInputRequired) as caught:
        p.discover_attractions("大同")
    assert caught.value.payload["code"] == "landmark_unverified"
    assert caught.value.payload["diagnostics"]["places"] == ["云冈石窟"]


def test_great_wall_segments_share_experience_not_identity():
    badaling, mutianyu = metadata("北京", "八达岭长城"), metadata("北京", "慕田峪长城")
    assert badaling["experience_group"] == mutianyu["experience_group"]
    assert badaling["identity_source"] != mutianyu["identity_source"]
    assert not metadata("北京", "长城")


def test_model_order_is_preserved_over_nearest_sight():
    p = planner(
        selector=lambda ctx: {
            "attraction_ids": [x["poi_id"] for x in reversed(ctx["attractions"])],
            "restaurant_ids": [x["poi_id"] for x in ctx["restaurants"]],
            "notes": "",
            "unmet_requirements": [],
        }
    )
    plan = p.run()
    assert plan.days[1].attractions[0].poi_id == "BTEST14"
