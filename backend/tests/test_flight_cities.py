import re

import pytest
from backend.app.domain.flight_cities import FLIGHT_CITIES, SNAPSHOT, flight_city_code


@pytest.mark.parametrize("city", list(SNAPSHOT["cities"]))
def test_every_sourced_city_and_city_suffix_resolves(city):
    assert re.fullmatch(r"[A-Z]{3}", flight_city_code(city))
    assert flight_city_code(city + "市") == flight_city_code(city)
    assert all("机场" in airport["name"] for airport in SNAPSHOT["cities"][city]["airports"])


@pytest.mark.parametrize("name,code", [
    ("深圳", "SZX"), (" 武汉市 ", "WUH"), ("北京", "BJS"), ("上海", "SHA"),
    ("成都", "CTU"), ("西安", "SIA"), ("杭州", "HGH"), ("乌鲁木齐", "URC"),
    ("拉萨", "LXA"), ("哈尔滨", "HRB"), ("香格里拉", "DIG"), ("揭阳", "SWA"),
    ("扬州", "YTY"), ("泰州", "YTY"), ("台州", "HYN"), ("泉州", "JJN"),
    ("郴州", "HCZ"), ("鄂州", "EHU"), ("嘉兴", "JNH"),
])
def test_city_codes_aliases_and_multi_airport_cities(name, code):
    assert flight_city_code(name) == code


@pytest.mark.parametrize("name", ["不存在的城市", "东莞", "北京大兴", "PKX", "大安", "伦敦", "香港"])
def test_no_guessed_nearby_airports_or_out_of_scope_cities(name):
    with pytest.raises(ValueError, match="不代表没有航班"):
        flight_city_code(name)


def test_ambiguous_city_has_specific_choices():
    with pytest.raises(ValueError, match="遵义新舟或遵义茅台"):
        flight_city_code("遵义")


def test_registry_has_nationwide_coverage_and_provenance():
    assert len(SNAPSHOT["cities"]) >= 250
    assert SNAPSHOT["source"] == "https://www.csair.com/comp/cityDate.json"
    assert len(SNAPSHOT["sha256"]) == 64
    assert len(FLIGHT_CITIES) > len(SNAPSHOT["cities"])
    assert {a["code"] for a in SNAPSHOT["cities"]["北京"]["airports"]} == {"PEK", "PKX"}
