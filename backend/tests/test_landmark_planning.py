from datetime import datetime

import httpx
import pytest
from backend.app.agents.journey_graph.nodes.validate import _validate_routes
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


def test_verified_landmark_parent_dedup_does_not_collapse_city_temples():
    rows = [poi("云冈石窟", 1), {**poi("云冈石窟-第十窟", 2), "parent": "BLAND1"}, poi("大同古城", 3), {**poi("华严寺", 4), "parent": "BLAND3"}]
    ranked = rank_amap_pois({"status": "1", "pois": rows}, "大同")
    assert {item.name for item in ranked} == {"云冈石窟", "大同古城", "华严寺"}
    assert "云冈石窟-第十窟" not in {item.name for item in ranked}


def lijiang_rows():
    # IDs and parent links from the 2026-09-18 mobile candidate response.
    return [
        {**poi(name, i), "id": identifier, "parent": parent, "cityname": "丽江市"}
        for i, (name, identifier, parent) in enumerate([
            ("玉龙雪山国家级风景名胜区", "B0378008FA", ""),
            ("玉龙雪山观景湖", "B0K6DS8TXV", "B0HBXXU1MR"),
            ("玉龙雪山国家级风景名胜区-玉液湖", "B037814YDS", "B0378157WA"),
            ("玉龙雪山冰川博物馆", "B0FFFDR6FE", "B03780I3SU"),
            ("独立博物馆", "independent", ""),
        ])
    ]


def test_mobile_lijiang_candidates_keep_one_core_experience():
    ranked = rank_amap_pois({"status": "1", "pois": lijiang_rows()}, "丽江")
    assert [p.name for p in ranked] == ["玉龙雪山国家级风景名胜区", "独立博物馆"]
    assert ranked[0].recommended_minutes == 360


def test_multilevel_parent_resolution_and_group_exclusion():
    rows = [poi("云冈石窟", 1),
            {**poi("中间分区", 2), "parent": "BLAND1"},
            {**poi("具体洞窟", 3), "parent": "BLAND2"}]
    assert len(rank_amap_pois({"status": "1", "pois": rows[::-1]}, "大同")) == 1
    assert not rank_amap_pois({"status": "1", "pois": rows}, "大同", avoid=["具体洞窟"])


def test_parent_cycles_and_cross_city_links_do_not_merge():
    rows = [poi("云冈石窟", 1),
            {**poi("异地地点", 2), "parent": "BLAND1", "cityname": "北京"},
            {**poi("循环甲", 3), "parent": "BLAND4"},
            {**poi("循环乙", 4), "parent": "BLAND3"}]
    assert len(rank_amap_pois({"status": "1", "pois": rows}, "大同")) == 4


def test_unverified_similar_name_is_retained_but_not_default_selected():
    rows = lijiang_rows() + [poi("玉龙雪山远眺观景台", 90)]
    provider = AmapAttractionDiscoveryProvider("fake", client=httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "1", "pois": rows}))))
    page = provider.discover("丽江", days=5)
    pending = next(p for p in page.items if p.name == "玉龙雪山远眺观景台")
    assert not pending.experience_group
    assert pending.experience_review_required
    assert pending.poi_id not in page.default_selected_ids


@pytest.mark.parametrize("excluded", [[], ["玉龙雪山观景湖"]])
def test_lijiang_planner_dedup_and_exclusion_across_queries(excluded):
    p, _ = landmark_planner(LANDMARKS[1], excluded_attractions=excluded)
    original = p.maps
    def search(city, keyword, kind):
        if kind != "110000":
            return original(city, keyword, kind)
        return {"status": "1", "pois": lijiang_rows() + [poi("玉龙雪山远眺观景台", 90)]}
    p.maps = search
    selected = p.discover_attractions("丽江")
    snow = [item for item in selected if item.get("experience_group") == "lijiang-snow-mountain"]
    assert len(snow) == (0 if excluded else 1)
    if snow:
        assert snow[0]["name"] == "玉龙雪山国家级风景名胜区"
    assert not any(item["name"] == "玉龙雪山远眺观景台" for item in selected)


def test_lijiang_explicit_component_conflict_pauses_before_queries():
    p, queries = landmark_planner(LANDMARKS[1], must_visit=["玉龙雪山", "玉龙雪山观景湖"])
    with pytest.raises(PlanningInputRequired) as caught:
        p.discover_attractions("丽江")
    assert caught.value.payload["code"] == "duplicate_must_visit"
    assert not queries


def test_planner_resolves_ancestry_across_separate_query_responses():
    p, _ = landmark_planner(LANDMARKS[3])
    def search(city, keyword, kind):
        if keyword == "云冈石窟":
            rows = [poi("云冈石窟", 1)]
        elif keyword == "大同城市地标":
            rows = [{**poi("中间分区", 2), "parent": "BLAND1"}]
        else:
            rows = [{**poi("独立命名的洞窟", 3), "parent": "BLAND2"}]
        return {"status": "1", "pois": rows}
    p.maps = search
    selected = p.discover_attractions("大同")
    assert [item["name"] for item in selected] == ["云冈石窟"]


def test_real_lijiang_group_scheduled_once_for_whole_trip():
    p, _ = landmark_planner(LANDMARKS[1])
    original = p.maps
    p.maps = lambda city, keyword, kind: (
        {"status": "1", "pois": lijiang_rows()} if kind == "110000"
        else original(city, keyword, kind)
    )
    plan = p.run()
    visits = [sight for day in plan.days for sight in day.attractions
              if same_experience("丽江", sight.name, "玉龙雪山")]
    assert len(visits) == 1
    assert visits[0].name == "玉龙雪山国家级风景名胜区"
    assert visits[0].visit_duration == 360


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


def test_real_amap_empty_railway_shape_is_not_a_train_segment():
    payload = transit({})
    segment = payload["route"]["transits"][0]["segments"][0]
    segment["railway"] = {"via_stops": [], "alters": [], "spaces": []}
    segment["taxi"] = []
    assert choose_transit(payload)["minutes"] == 45
    segment["railway"]["name"] = "实际铁路"
    assert choose_transit(payload) is None


@pytest.mark.parametrize("invalid", ["missing_bus", "multiple_sights", "transfer_day", "missing_rest"])
def test_dedicated_day_long_bus_round_trip_passes_route_validation(invalid):
    p, _ = landmark_planner(LANDMARKS[3])
    def long_transit(args):
        payload = transit(args)
        payload["route"]["transits"][0]["duration"] = "5700"
        return payload
    p.transit = long_transit
    plan = p.run()
    issues = _validate_routes({"request": p.request}, plan)
    assert not any(issue.code == "daily_commute_excessive" for issue in issues)
    assert any(issue.code == "daily_commute_high" for issue in issues)
    bus_routes = [route for route in plan.route_matrix if route.provider == "amap-transit"]
    assert len(bus_routes) == 2
    day = next(day for day in plan.days if any(item.route_estimate_id == bus_routes[0].estimate_id for item in day.timeline))
    if invalid == "missing_bus":
        bus_routes[1].provider = "local-estimate"
    elif invalid == "multiple_sights":
        day.attractions.append(day.attractions[0].model_copy())
    elif invalid == "transfer_day":
        day.is_transfer_day = True
        bus_item = next(item for item in day.timeline if item.route_estimate_id == bus_routes[0].estimate_id)
        bus_item.duration_minutes += 30
    else:
        for item in day.timeline:
            if item.item_type == "free_time":
                item.duration_minutes = 30
    assert any(issue.code == "daily_commute_excessive" for issue in _validate_routes({"request": p.request}, plan))


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
