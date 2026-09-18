"""Refresh the reviewed mainland aviation-city snapshot, without paid API calls."""

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.request import urlopen

SOURCE = "https://www.csair.com/comp/cityDate.json"
OUTPUT = Path(__file__).resolve().parents[1] / "app/domain/data/flight_cities.json"
# The airline also uses internal ground-transport city identifiers for new airports.
# Keep distinct established metropolitan codes; use the attached aviation code for
# these reviewed single-airport entries rather than forwarding railway identifiers.
OVERRIDES = {"昌吉": "JBK", "郴州": "HCZ", "鄂州": "EHU", "吉首": "DXJ", "嘉兴": "JNH"}
ALIASES = {
    "香格里拉": "迪庆", "迪庆藏族自治州": "迪庆", "德宏": "芒市",
    "德宏傣族景颇族自治州": "芒市", "揭阳": "揭阳潮汕", "潮州": "揭阳潮汕",
    "扬州": "扬州泰州", "泰州": "扬州泰州", "呼伦贝尔": "海拉尔",
    "西双版纳傣族自治州": "西双版纳", "景洪": "西双版纳",
    "湘西": "吉首", "湘西土家族苗族自治州": "吉首", "奇台": "昌吉",
}


def build(raw):
    cities = {}
    for row in json.loads(raw)["cityList"]:
        if row[4] != "CN" or row[3] != "N":
            continue
        name = row[7][0]
        airports = [{"code": a[0], "name": a[1][0]} for a in row[8]
                    if "机场" in a[1][0] and not any(x in a[1][0] for x in ("候机楼", "大巴", "车站"))]
        # Upstream incorrectly attaches Chongqing Liangping to Da'an (Jilin).
        if not airports or name == "大安":
            continue
        code = OVERRIDES.get(name, row[0])
        if not re.fullmatch(r"[A-Z]{3}", code):
            raise ValueError(f"Invalid aviation code for {name}")
        cities[name] = {"code": code, "airports": airports}
    assert len(cities) >= 240, "Unexpected source coverage regression"
    assert cities["北京"]["code"] == "BJS" and cities["西安"]["code"] == "SIA"
    assert all(target in cities for target in ALIASES.values())
    return {"source": SOURCE, "retrieved_on": date.today().isoformat(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "scope": "mainland aviation cities; not a schedule or sale guarantee",
            "cities": dict(sorted(cities.items())), "aliases": ALIASES}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Replace the snapshot for review")
    args = parser.parse_args()
    with urlopen(SOURCE, timeout=30) as response:
        snapshot = build(response.read())
    print(f"Validated {len(snapshot['cities'])} cities from {SOURCE}")
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
