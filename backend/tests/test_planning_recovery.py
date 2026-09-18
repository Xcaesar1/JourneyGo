from datetime import timedelta

import pytest
from backend.app.services.travel_ledger import QueryReuseUnavailable
from backend.app.services.travel_place_selection import PlaceSelection, selection_notices
from backend.tests.test_one_click_travel import maps, planner, request, supplier


def selection(**changes):
    return PlaceSelection(
        attraction_ids=["B001"], restaurant_ids=["B002"], notes="", unmet_requirements=[], **changes
    )


def test_invented_requirement_cannot_pause():
    selected = selection(
        requirement_issues=[
            {
                "request_field": "accessibility_needs",
                "request_quote": "轮椅",
                "severity": "blocking",
                "message": "无设施证据",
            }
        ]
    )
    assert selection_notices(selected, request())[1] == []


def test_ordinary_preference_is_advisory_and_explicit_constraint_blocks():
    for text, blocking in [("喜欢历史文化", False), ("必须无障碍通行", True)]:
        selected = selection(
            requirement_issues=[
                {
                    "request_field": "free_text_input",
                    "request_quote": text,
                    "severity": "blocking",
                    "message": "无法核实",
                }
            ]
        )
        assert bool(selection_notices(selected, request(free_text_input=text))[1]) == blocking
    assert selection_notices(selection(), request(accessibility_needs=["轮椅通行"]))[1]


@pytest.mark.parametrize("text", ["花生过敏", "轮椅出行", "I have a peanut allergy"])
def test_safety_requirements_not_silently_dropped_when_model_omits_issues(text):
    assert selection_notices(selection(), request(free_text_input=text))[1]


@pytest.mark.parametrize(
    "text", ["没有过敏，喜欢历史文化", "不需要无障碍设施", "No food allergies"]
)
def test_absent_safety_needs_do_not_block(text):
    assert not selection_notices(selection(), request(free_text_input=text))[1]


def test_two_sights_three_day_arrival_and_departure_do_not_pause():
    base = request()
    r = type(base).model_validate(
        {
            **base.model_dump(),
            "origin": "深圳",
            "destinations": [{"city": "上海", "days": 3}],
            "travel_days": 3,
            "end_date": base.start_date + timedelta(days=2),
            "interests": ["历史文化", "美食"],
        }
    )
    calls, contexts = [], []

    def two_sights(city, keyword, kind):
        calls.append((keyword, kind))
        data = maps(city, keyword, kind)
        if kind == "110000":
            data["pois"] = data["pois"][:2]
            for row, name in zip(data["pois"], ["城隍庙", "豫园"]):
                row["name"] = name
        return data

    def trains(provider, tool, args):
        data = supplier(provider, tool, args)
        if provider == "train":
            data[0]["start_time"] = "06:46" if args["fromStation"] == "深圳" else "09:50"
            data[0]["arrive_time"] = "18:44" if args["fromStation"] == "深圳" else "21:27"
        return data

    def select(context):
        contexts.append(context)
        return {
            "attraction_ids": [p["poi_id"] for p in context["attractions"]],
            "restaurant_ids": [p["poi_id"] for p in context["restaurants"]],
            "notes": "",
            "unmet_requirements": ["两个景点无法覆盖三天", "未提供无障碍证据", "未提供饮食保证"],
        }

    plan = planner(r, maps=two_sights, supplier=trains, selector=select).run()
    assert len(plan.days) == 3
    assert len(plan.days[1].attractions) == 2
    assert not plan.days[0].attractions and not plan.days[2].attractions
    assert "往返交通占比较高" in plan.overall_suggestions
    assert "无障碍证据" not in plan.overall_suggestions
    assert len([c for c in calls if c[1] == "110000"]) <= 3
    assert all("美食" not in k for k, kind in calls if kind == "110000")
    windows = contexts[0]["activity_windows"]
    assert windows[2]["available_minutes"] == 0
    assert windows[1]["available_minutes"] > windows[0]["available_minutes"]


def test_bounded_supplement_stops_when_enough_and_deduplicates():
    calls = []
    p = planner(request(interests=["历史文化", "美食"]))

    def pois(city, keyword, kind, **kwargs):
        calls.append(keyword)
        count = 2 if keyword == "历史文化" else 12
        return [{"poi_id": f"B{i}", "name": f"景点{i}"} for i in range(count)]

    p.pois = pois
    result = p.discover_attractions("上海")
    assert len(result) == 12 and len(calls) == 2


def test_model_only_recovery_uses_old_mixed_query_without_new_queries():
    p = planner(request(interests=["历史文化", "美食"], quote_revision={"model": 1}))

    class CachedLedger:
        def execute(self, provider, scope, args, call):
            if args["keyword"] == "历史文化 美食":
                data = maps(args["city"], args["keyword"], args["kind"])
                data["pois"] = data["pois"][:2]
                return data
            raise QueryReuseUnavailable(provider, scope)

    p.ledger = CachedLedger()
    p.maps = lambda *_: pytest.fail("Recovery must not issue a new external query")
    assert len(p.discover_attractions("上海")) == 2


def test_empty_pool_pauses_without_inventing_sights():
    p = planner()
    p.maps = lambda *_: {"status": "1", "pois": []}
    from backend.app.services.travel_ledger import PlanningInputRequired

    with pytest.raises(PlanningInputRequired) as failure:
        p.discover_attractions("上海")
    assert failure.value.payload["code"] == "no_places"
