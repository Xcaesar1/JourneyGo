from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from backend.app.agents.journey_graph import build_journey_graph
from backend.app.config import Settings
from backend.app.domain.trip_models import TripRequestV2
from backend.app.services.one_click_travel import OneClickPlanner, preflight
from backend.app.services.travel_ledger import PlanningInputRequired


def request(**changes):
    start = datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
    return TripRequestV2.model_validate(
        dict(
            origin="上海",
            destinations=[{"city": "西安", "days": 5}],
            start_date=start,
            end_date=start + timedelta(days=4),
            travel_days=5,
            budget_total="10000",
            planning_mode="one_click",
            **changes,
        )
    )


def settings():
    return Settings(
        _env_file=None,
        one_click_travel_enabled=True,
        vite_amap_web_key="test-only-map-key",
        OPENAI_API_KEY="test-only-model-key",
        OPENAI_BASE_URL="https://model.example/v1",
        OPENAI_MODEL="test-model",
        planner_engine="journey_graph",
        travel_train_enabled=True,
        travel_hotel_enabled=True,
        rollinggo_api_key="fake-key",
        demo_mode=False,
    )


class Ledger:
    def __init__(self):
        self.records = []
        self.results = {}

    def execute(self, provider, scope, args, call):
        key = str((provider, scope, args))
        if key not in self.results:
            self.results[key] = call()
            self.records.append(
                {"provider": provider, "scope": scope, "fetched_at": "2026-09-17T00:00:00Z"}
            )
        return self.results[key]


def supplier(provider, tool, args):
    if provider == "train":
        return [
            {
                "start_train_code": "G123",
                "start_date": args["date"],
                "arrive_date": args["date"],
                "from_station": args["fromStation"] + "站",
                "to_station": args["toStation"] + "站",
                "start_time": "08:00" if args["fromStation"] == "上海" else "14:00",
                "arrive_time": "14:00" if args["fromStation"] == "上海" else "20:00",
                "prices": [{"seat_name": "二等座", "num": "有", "price": "669.50"}],
            }
        ]
    if tool == "searchHotels":
        assert args["size"] == 10 and args["filterOptions"]["starRatings"] == [3, 4.5]
        return {
            "success": True,
            "hotelInformationList": [
                {
                    "hotelId": 1,
                    "name": "测试商务酒店",
                    "starRating": 4,
                    "price": {"lowestPrice": 350},
                }
            ],
        }
    return {
        "success": True,
        "hotelId": 1,
        "checkIn": args["dateParam"]["checkInDate"],
        "checkOut": args["dateParam"]["checkOutDate"],
        "roomRatePlans": [
            {
                "roomName": "商务房",
                "ratePlanId": "test-room",
                "averagePrice": 350,
                "currency": "CNY",
                "isOnRequest": False,
                "roomInfo": {"maxOccupancy": 2},
            }
        ],
    }


def maps(city, keyword, kind):
    count = 15 if kind == "110000" else 2 if kind == "050100" else 1
    return {
        "status": "1",
        "pois": [
            {
                "name": keyword if count == 1 else f"{keyword}{i}",
                "id": f"BTEST{i}",
                "address": "模拟地址",
                "adcode": "610100",
                "location": f"108.95,{34.26 + i * 0.001}",
            }
            for i in range(count)
        ],
    }


def planner(r=None, **overrides):
    return OneClickPlanner(
        "test-trip",
        r or request(),
        settings(),
        ledger=Ledger(),
        **{
            "supplier": supplier,
            "maps": maps,
            "selector": lambda ctx: {
                "attraction_ids": [p["poi_id"] for p in ctx["attractions"]],
                "restaurant_ids": [p["poi_id"] for p in ctx["restaurants"]],
                "notes": "模拟规划",
                "unmet_requirements": [],
            },
            **overrides,
        },
    )


@pytest.mark.parametrize("adults", [1, 2])
def test_shanghai_xian_five_days(adults):
    r = request(travelers=adults)
    plan = planner(r).run()
    summary = plan.travel_summary
    assert summary["known_cents"] == 133900 * adults
    assert summary["hotel"]["cost_cents"] == 140000
    assert summary["hotel"]["nights"] == 4
    assert sum(day.hotel is not None for day in plan.days) == 4
    assert summary["cost_items"][-1]["amount_cents"] is None
    assert all(meal.poi_id for day in plan.days for meal in day.meals)
    assert all(
        a.end <= b.start for day in plan.days for a, b in zip(day.timeline, day.timeline[1:])
    )


def test_one_click_uses_existing_graph():
    r = request()
    graph = build_journey_graph(one_click_planner=lambda state: planner(r).run())
    result = graph.invoke({"request": r, "task_id": "t", "trip_id": "p"})
    assert result["final_plan"].travel_summary["hotel"]["nights"] == 4
    assert not result["validation_report"].has_critical


def test_hotel_photos_survive_non_attraction_poi_parsing():
    def with_photos(city, keyword, kind):
        result = maps(city, keyword, kind)
        for row in result['pois']:
            row['photos'] = [{'url': 'https://example.test/hotel.jpg'}]
        return result
    hotel = planner(maps=with_photos).pois('西安', '测试酒店', '100100', exact=True)[0]
    assert hotel['image']['url'] == 'https://example.test/hotel.jpg'
    assert hotel['image']['source'] == 'amap'


@pytest.mark.parametrize("available", [True, False])
def test_one_click_collects_trip_date_weather_without_changing_verified_plan(
    monkeypatch, available
):
    from backend.app.services import weather

    r = request()
    original = planner(r).run()
    calls = []

    def collect(city, start, end):
        calls.append((city, start, end))
        rows = (
            [
                {
                    "city": city,
                    "date": (start + timedelta(days=i)).isoformat(),
                    "day_temp": 25,
                    "night_temp": 18,
                    "precipitation_probability": 0,
                    "source_url": "https://open-meteo.com/",
                    "fetched_at": "2026-09-17T00:00:00Z",
                }
                for i in range((end - start).days + 1)
            ]
            if available
            else []
        )
        return rows, "complete" if available else "weather_unavailable"

    monkeypatch.setattr(weather.WeatherProvider, "collect", lambda self, *args: collect(*args))
    config = settings().model_copy(update={"weather_enabled": True})
    result = build_journey_graph(
        one_click_planner=lambda state: original,
        weather_settings=config,
    ).invoke({"request": r, "task_id": "t", "trip_id": "p"})
    plan = result["final_plan"]
    assert calls == [("西安", r.start_date, r.end_date)]
    assert len(plan.weather_info) == (5 if available else 0)
    assert plan.travel_summary == original.travel_summary
    assert plan.days == original.days
    assert plan.budget == original.budget
    assert result["metrics"]["weather_status"]["西安"] == (
        "complete" if available else "weather_unavailable"
    )
    if available:
        assert [row.date for row in plan.weather_info] == [day.date for day in plan.days]
        assert plan.weather_info[0].precipitation_probability == 0


def test_return_outside_sale_window_rejected_before_dispatch():
    r = request()
    shift = timedelta(days=12)
    r = r.model_copy(update={"start_date": r.start_date + shift, "end_date": r.end_date + shift})
    with pytest.raises(ValueError, match="15"):
        preflight(r, settings())


@pytest.mark.parametrize("failure", ["sold_out", "no_hotel", "no_quote", "poi", "budget"])
def test_missing_evidence_pauses(failure):
    def broken(provider, tool, args):
        data = supplier(provider, tool, args)
        if failure == "sold_out" and provider == "train":
            data[0]["prices"][0]["num"] = "无"
        if failure == "no_hotel" and tool == "searchHotels":
            data["hotelInformationList"] = []
        if failure == "no_quote" and tool == "getHotelDetail":
            data["roomRatePlans"][0].pop("averagePrice")
        return data

    p = planner(
        supplier=broken,
        maps=(lambda *args: {"status": "1", "pois": []}) if failure == "poi" else maps,
    )
    if failure == "budget":
        p.request.budget_total = 100
    with pytest.raises(PlanningInputRequired):
        p.run()


@pytest.mark.parametrize(
    "case",
    ["late_arrival", "early_return", "two_seats", "hotel_full", "invented_poi", "special_needs"],
)
def test_hard_constraints_cannot_be_fabricated(case):
    def changed(provider, tool, args):
        data = supplier(provider, tool, args)
        if provider == "train":
            if case == "late_arrival" and args["fromStation"] == "上海":
                data[0]["arrive_time"] = "23:50"
            if case == "early_return" and args["fromStation"] != "上海":
                data[0]["start_time"] = "00:30"
            if case == "two_seats":
                data[0]["prices"][0]["num"] = "1"
        if case == "hotel_full" and tool == "getHotelDetail":
            data["roomRatePlans"][0]["isOnRequest"] = True
        return data

    def selection(ctx):
        return {
            "attraction_ids": ["INVENTED"]
            if case == "invented_poi"
            else [p["poi_id"] for p in ctx["attractions"]],
            "restaurant_ids": [p["poi_id"] for p in ctx["restaurants"]],
            "notes": "test",
            "unmet_requirements": ["无障碍设施未核实"] if case == "special_needs" else [],
        }

    with pytest.raises(PlanningInputRequired):
        planner(
            request(
                travelers=2, accessibility_needs=["轮椅无障碍"] if case == "special_needs" else []
            ),
            supplier=changed,
            selector=selection,
        ).run()


def test_hotel_detail_bound_and_list_reference_fallback():
    details = []

    def many(provider, tool, args):
        data = supplier(provider, tool, args)
        if tool == "searchHotels":
            data["hotelInformationList"] = [
                {
                    "hotelId": i,
                    "name": "测试商务酒店",
                    "starRating": 4,
                    "price": {"lowestPrice": 350, "hasPrice": True, "currency": "CNY"},
                }
                for i in range(1, 11)
            ]
        if tool == "getHotelDetail":
            details.append(args["hotelId"])
            data["hotelId"] = args["hotelId"]
            data["roomRatePlans"][0].pop("averagePrice")
        return data

    result = planner(supplier=many).run()
    assert details == [1, 2, 3]
    assert result.travel_summary["hotel"]["cost_cents"] == 140000
    assert "首夜参考价" in result.travel_summary["hotel"]["pricing_note"]


def test_hotel_location_and_compact_schedule_beat_cheaper_outskirts():
    detailed = []

    def four_hotels(provider, tool, args):
        data = supplier(provider, tool, args)
        if tool == "searchHotels":
            data["hotelInformationList"] = [
                {
                    "hotelId": 1,
                    "name": "远郊商务酒店一",
                    "starRating": 4,
                    "price": {"lowestPrice": 180},
                },
                {
                    "hotelId": 2,
                    "name": "远郊商务酒店二",
                    "starRating": 4,
                    "price": {"lowestPrice": 200},
                },
                {
                    "hotelId": 3,
                    "name": "远郊商务酒店三",
                    "starRating": 4,
                    "price": {"lowestPrice": 220},
                },
                {
                    "hotelId": 4,
                    "name": "市区商务酒店",
                    "starRating": 4,
                    "price": {"lowestPrice": 420},
                },
            ]
        elif tool == "getHotelDetail":
            detailed.append(args["hotelId"])
            data["hotelId"] = args["hotelId"]
            data["roomRatePlans"][0]["averagePrice"] = {
                1: 180,
                2: 200,
                3: 220,
                4: 420,
            }[args["hotelId"]]
        return data

    def spread_maps(city, keyword, kind):
        if kind == "100100":
            longitude, latitude = (
                (109.30, 34.42) if keyword.startswith("远郊商务酒店") else (108.95, 34.26)
            )
            names = [keyword]
            locations = [(longitude, latitude)]
        elif kind == "110000":
            names = [
                *[f"市区景点{i}" for i in range(8)],
                *[f"远郊景点{i}" for i in range(6)],
            ]
            locations = [
                *[(108.94 + i * 0.002, 34.25 + i * 0.001) for i in range(8)],
                *[(109.31 + i * 0.001, 34.43) for i in range(6)],
            ]
        elif kind == "050100":
            names = [*[f"市区餐厅{i}" for i in range(4)], *[f"远郊餐厅{i}" for i in range(3)]]
            locations = [
                *[(108.95 + i * 0.001, 34.26) for i in range(4)],
                *[(109.31 + i * 0.001, 34.43) for i in range(3)],
            ]
        else:
            names = [keyword]
            locations = [(108.94, 34.27)]
        return {
            "status": "1",
            "pois": [
                {
                    "name": name,
                    "id": f"B{kind}{index}",
                    "address": "模拟地址",
                    "adcode": "610100" if city == "西安" else "310000",
                    "location": f"{longitude},{latitude}",
                }
                for index, (name, (longitude, latitude)) in enumerate(zip(names, locations))
            ],
        }

    def ranked_shortlist(ctx):
        return {
            "attraction_ids": [place["poi_id"] for place in ctx["attractions"]],
            "restaurant_ids": [place["poi_id"] for place in ctx["restaurants"]],
            "notes": "模拟规划",
            "unmet_requirements": [],
        }

    plan = planner(supplier=four_hotels, maps=spread_maps, selector=ranked_shortlist).run()

    assert len(detailed) == 3 and 4 in detailed
    assert plan.travel_summary["hotel"]["name"] == "市区商务酒店"
    assert plan.travel_summary["hotel"]["cost_cents"] == 168000
    scheduled = [place.name for day in plan.days for place in day.attractions]
    assert scheduled
    assert not any(name.startswith("远郊景点") for name in scheduled)
    omitted = plan.travel_summary["selection_adjustments"]["omitted_preferred_places"]
    assert "远郊景点0" in omitted
    assert "远郊景点0" in plan.overall_suggestions


def test_scheduler_falls_back_to_verified_hotel_before_model_selection():
    details = []
    selection_contexts = []

    def two_hotels(provider, tool, args):
        data = supplier(provider, tool, args)
        if tool == "searchHotels":
            data["hotelInformationList"] = [
                {
                    "hotelId": 1,
                    "name": "景区商务酒店",
                    "starRating": 4,
                    "price": {"lowestPrice": 300},
                },
                {
                    "hotelId": 2,
                    "name": "枢纽商务酒店",
                    "starRating": 4,
                    "price": {"lowestPrice": 320},
                },
            ]
        elif tool == "getHotelDetail":
            details.append(args["hotelId"])
            data["hotelId"] = args["hotelId"]
            data["roomRatePlans"][0]["averagePrice"] = {
                1: 300,
                2: 320,
            }[args["hotelId"]]
        return data

    def fallback_maps(city, keyword, kind):
        if kind == "100100":
            locations = {
                "景区商务酒店": (109.60, 34.55),
                "枢纽商务酒店": (108.95, 34.26),
            }
            names = [keyword]
            coordinates = [locations[keyword]]
        elif kind == "110000":
            names = [*[f"景区景点{i}" for i in range(8)], "枢纽景点一", "枢纽景点二"]
            coordinates = [
                *[(109.60 + i * 0.001, 34.55) for i in range(8)],
                (108.951, 34.261),
                (108.952, 34.262),
            ]
        elif kind == "050100":
            names = [*[f"景区餐厅{i}" for i in range(4)], "枢纽餐厅"]
            coordinates = [
                *[(109.60 + i * 0.001, 34.551) for i in range(4)],
                (108.951, 34.260),
            ]
        else:
            names = [keyword]
            coordinates = [(108.95, 34.26)]
        return {
            "status": "1",
            "pois": [
                {
                    "name": name,
                    "id": f"B{kind}{index}{place_name}",
                    "address": "模拟地址",
                    "adcode": "610100" if city == "西安" else "310000",
                    "location": f"{longitude},{latitude}",
                }
                for index, (name, place_name, (longitude, latitude)) in enumerate(
                    zip(names, names, coordinates)
                )
            ],
        }

    def select_once(context):
        selection_contexts.append(context)
        return {
            "attraction_ids": [place["poi_id"] for place in context["attractions"]],
            "restaurant_ids": [place["poi_id"] for place in context["restaurants"]],
            "notes": "模拟规划",
            "unmet_requirements": [],
        }

    plan = planner(supplier=two_hotels, maps=fallback_maps, selector=select_once).run()

    assert details == [1, 2]
    assert len(selection_contexts) == 1
    assert selection_contexts[0]["hotel"]["hotel_id"] == 2
    assert plan.travel_summary["hotel"]["name"] == "枢纽商务酒店"
    assert plan.travel_summary["hotel"]["cost_cents"] == 128000
    fallback = plan.travel_summary["selection_adjustments"]["hotel_fallback"]
    assert fallback["from_hotel_id"] == 1
    assert fallback["to_hotel_id"] == 2
    assert "local_transfer_excessive" in fallback["reason_codes"]
    assert "已改用同批核验的备选酒店" in plan.overall_suggestions


def test_intercity_train_and_local_transit_do_not_count_as_walking():
    from backend.app.agents.journey_graph.nodes.validate import _validate_routes

    r = request(max_daily_walking_minutes=1)
    plan = planner(r).run()
    train_route = next(route for route in plan.route_matrix if route.provider == "train")
    extended_route = train_route.model_copy(update={"duration_minutes": 900})
    days = []
    for day in plan.days:
        days.append(
            day.model_copy(
                update={
                    "timeline": [
                        item.model_copy(update={"duration_minutes": 900})
                        if item.route_estimate_id == train_route.estimate_id
                        else item
                        for item in day.timeline
                    ]
                }
            )
        )
    plan = plan.model_copy(
        update={
            "days": days,
            "route_matrix": [
                extended_route if route.estimate_id == train_route.estimate_id else route
                for route in plan.route_matrix
            ],
        }
    )

    codes = {issue.code for issue in _validate_routes({"request": r}, plan)}
    assert "daily_commute_excessive" not in codes
    assert "walking_limit_exceeded" not in codes


def test_exact_poi_name_wins_over_fuzzy_provider_order():
    def fuzzy_first(city, keyword, kind):
        return {
            "status": "1",
            "pois": [
                {
                    "name": "大雁塔北广场",
                    "id": "BFUZZY",
                    "address": "模拟地址",
                    "adcode": "610100",
                    "location": "108.96,34.22",
                },
                {
                    "name": "大 雁 塔",
                    "id": "BEXACT",
                    "address": "模拟地址",
                    "adcode": "610100",
                    "location": "108.96,34.21",
                },
            ],
        }

    result = planner(maps=fuzzy_first).pois("西安", "大雁塔", "110000", exact=True)
    assert result[0]["poi_id"] == "BEXACT"


def test_replan_quote_revision_changes_only_with_refresh_token():
    from backend.app.domain.review_models import ReplanRequestV2
    from backend.app.services.one_click_travel import (
        preserve_replan_quote_revisions,
        replan_quote_revision,
        replan_request,
    )

    first = replan_quote_revision("thread-1", "refresh-1")
    assert first == replan_quote_revision("thread-1", "refresh-1")
    assert first != replan_quote_revision("thread-1", "refresh-2")
    base = request()
    hotel_change = ReplanRequestV2(
        instruction="更新酒店",
        refresh_travel="hotel",
        refresh_token="refresh-1",
    )
    carried = preserve_replan_quote_revisions(base, hotel_change, "thread-1")
    amap_change = ReplanRequestV2(
        instruction="更新地点",
        refresh_travel="amap",
        refresh_token="refresh-2",
    )
    updated = replan_request(
        carried,
        amap_change,
        replan_quote_revision("thread-1", "refresh-2"),
    )
    assert updated.quote_revision == {
        "hotel": replan_quote_revision("thread-1", "refresh-1"),
        "amap": replan_quote_revision("thread-1", "refresh-2"),
    }


def test_replan_flight_refresh_requires_new_consent():
    from backend.app.domain.review_models import ReplanRequestV2
    from backend.app.services.one_click_travel import replan_request

    old = request(intercity_mode="flight", flight_confirmed=True)
    changes = ReplanRequestV2(instruction="Refresh travel proposal", refresh_travel="flight")
    with pytest.raises(ValueError, match="consent"):
        replan_request(old, changes, 1)
    changes.confirm_flight_queries = True
    updated = replan_request(old, changes, 1)
    assert updated.quote_revision == {"flight": 1}
    assert old.quote_revision == {}
    hotel_only = replan_request(
        old, ReplanRequestV2(instruction="Refresh travel proposal", refresh_travel="hotel"), 2
    )
    assert hotel_only.quote_revision == {"hotel": 2}
    secured_original = old.model_copy(update={"quote_revision": {"hotel": 2, "model": 3}})
    replacement = request(
        intercity_mode="flight",
        flight_confirmed=True,
        quote_revision={"train": 99, "model": 99},
    )
    preserved = replan_request(
        secured_original,
        ReplanRequestV2(instruction="调整景点", travel_request=replacement),
        4,
    )
    assert preserved.quote_revision == {"hotel": 2, "model": 3}


def test_flight_roundtrip_once_each_and_unknown_taxes():
    from pydantic import SecretStr

    calls = []

    def flights(provider, tool, args):
        if provider != "flight":
            return supplier(provider, tool, args)
        calls.append(args)
        departure = datetime.fromisoformat(args["dep_date"] + "T09:00:00").replace(
            tzinfo=ZoneInfo("Asia/Shanghai")
        )
        return {
            "code": 200,
            "data": [
                {
                    "depcitycode": args["dep_city"],
                    "arrcitycode": args["arr_city"],
                    "depdate": args["dep_date"],
                    "flightno": "MU1234",
                    "depaptcname": "测试出发机场",
                    "arraptcname": "测试到达机场",
                    "flightdeptimeplandate": departure.timestamp(),
                    "flightarrtimeplandate": (departure + timedelta(hours=2)).timestamp(),
                    "cabins": [{"classname": "经济舱", "seatnum": "2", "price": "700.50"}],
                }
            ],
        }

    p = planner(request(intercity_mode="flight", flight_confirmed=True), supplier=flights)
    p.settings = p.settings.model_copy(
        update={
            "travel_flight_enabled": True,
            "variflight_api_key": SecretStr("fake-key"),
            "api_access_code": SecretStr("test-only-access"),
            "travel_flight_call_limit": 2,
        }
    )
    first = p.run()
    second = p.run()
    assert len(calls) == 2
    assert calls[0]["dep_city"] == "SHA" and calls[0]["arr_city"] == "SIA"
    assert first.travel_summary["cost_items"][-1] == {
        "category": "flight_taxes",
        "status": "unknown",
        "amount_cents": None,
    }
    assert second.travel_summary["known_cents"] == 140100


def test_fixed_september_20_five_day_acceptance(monkeypatch):
    from datetime import date

    from backend.app.services import one_click_travel

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 17, 9, tzinfo=tz)

    monkeypatch.setattr(one_click_travel, "datetime", Clock)
    r = request().model_copy(
        update={"start_date": date(2026, 9, 20), "end_date": date(2026, 9, 24)}
    )
    plan = planner(r).run()
    assert str(plan.end_date) == "2026-09-24"
    assert plan.travel_summary["expected_cents"] == 288900
    assert plan.travel_summary["hotel"]["nights"] == 4
    assert plan.travel_summary["hotel"]["cost_cents"] == 140000
    assert all(len({meal.type for meal in day.meals}) == len(day.meals) for day in plan.days)


def test_human_approval_and_legacy_adapter_preserve_logistics():
    from backend.app.adapters import trip_plan_v2_to_legacy
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command

    r = request()
    calls = []

    def verified(state):
        calls.append(1)
        return planner(r).run()

    graph = build_journey_graph(
        one_click_planner=verified, checkpointer=InMemorySaver(), require_human_review=True
    )
    config = {"configurable": {"thread_id": "one-click-approval"}}
    preview = graph.invoke({"request": r, "task_id": "t", "trip_id": "p"}, config)
    assert "final_plan" not in preview
    final = graph.invoke(Command(resume={"action": "approve"}), config)["final_plan"]
    assert calls == [1]
    legacy = trip_plan_v2_to_legacy(final)
    assert legacy.travel_summary == final.travel_summary
    assert legacy.days[0].hotel.poi_id == final.days[0].hotel.poi_id
    assert legacy.days[1].meals[0].poi_id == final.days[1].meals[0].poi_id
