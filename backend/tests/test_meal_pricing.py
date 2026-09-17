import pytest
from backend.app.adapters.trip_plan import trip_plan_v2_to_legacy
from backend.app.services.meal_pricing import meal_reference
from backend.tests.test_one_click_travel import maps, planner, request


@pytest.mark.parametrize("value", [None, "", [], "NaN", "Infinity", -1, 0, True, "免费", "60元起"])
def test_unknown_price_is_not_a_quote(value):
    assert (
        meal_reference({"business": {"cost": value}, "fetched_at": "2026-09-17T00:00:00Z"}) is None
    )


def test_price_needs_a_fetch_timestamp():
    assert meal_reference({"business": {"cost": "60"}}) is None


def test_cents_round_without_binary_float_loss():
    price = meal_reference({"business": {"cost": "45.675"}, "fetched_at": "2026-09-17T00:00:00Z"})
    assert price.amount_cents == 4568


def test_scheduled_meals_count_once_per_person():
    def priced_maps(city, keyword, kind):
        result = maps(city, keyword, kind)
        result["fetched_at"] = "2026-09-17T00:00:00Z"
        for poi in result["pois"]:
            poi["business"] = {"cost": "45.67"}
        return result

    plan = planner(request(travelers=2), maps=priced_maps).run()
    meals = [meal for day in plan.days for meal in day.meals]
    assert meals
    expected = 4567 * len(meals) * 2
    item = next(i for i in plan.travel_summary["cost_items"] if i["category"] == "meals")
    assert item["amount_cents"] == expected
    assert all(m.estimated_cost == 0 and m.price_reference.amount_cents == 4567 for m in meals)
    legacy = trip_plan_v2_to_legacy(plan)
    assert next(m for d in legacy.days for m in d.meals).price_reference.amount_cents == 4567
    assert plan.travel_summary["costs_complete"] is False


def test_missing_prices_excluded_from_ledger():
    plan = planner().run()
    item = next(i for i in plan.travel_summary["cost_items"] if i["category"] == "meals")
    assert item == {"category": "meals", "status": "unknown", "amount_cents": None}
    assert plan.budget.total_meals == 0
