"""Single offline source of aviation city codes for planning and quote forms."""

import json
from pathlib import Path

SNAPSHOT = json.loads((Path(__file__).parent / "data/flight_cities.json").read_text(encoding="utf-8"))
FLIGHT_CITIES = {name: item["code"] for name, item in SNAPSHOT["cities"].items()}
FLIGHT_CITIES.update({alias: FLIGHT_CITIES[target] for alias, target in SNAPSHOT["aliases"].items()})


def flight_city_code(city: str) -> str:
    name = city.strip()
    code = FLIGHT_CITIES.get(name) or FLIGHT_CITIES.get(name.removesuffix("市"))
    if code:
        return code
    if name.removesuffix("市") == "遵义":
        raise ValueError("请选择遵义新舟或遵义茅台，避免查询到错误机场。")
    raise ValueError(f"未匹配到“{city}”的航空城市，请填写机场所在城市或通航地名称；不代表没有航班，不会自动改查邻近城市。")
