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
        planner(request(travelers=2), supplier=changed, selector=selection).run()


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
    assert plan.travel_summary["expected_cents"] == 378900
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
