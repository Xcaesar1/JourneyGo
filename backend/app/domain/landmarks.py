"""Sourced identity rules, not a live popularity ranking or opening-hours feed."""

import re

LANDMARKS = [
    dict(
        city="上海",
        name="东方明珠广播电视塔",
        aliases=["东方明珠", "东方明珠塔", "东方明珠电视塔"],
        group="shanghai-pearl",
        minutes=120,
        style="standard",
        source="https://www.opg.cn/cn/companyIntroduction/index.html",
    ),
    dict(
        city="丽江",
        name="玉龙雪山",
        aliases=["玉龙雪山景区", "玉龙雪山国家级风景名胜区"],
        group="lijiang-snow-mountain",
        minutes=360,
        style="full_day",
        source="https://www.ynxc.gov.cn/uploadfile/s61/2024/0419/20240419094809765.pdf",
    ),
    dict(
        city="武汉",
        name="黄鹤楼",
        aliases=["黄鹤楼公园", "黄鹤楼景区"],
        group="wuhan-yellow-crane",
        minutes=120,
        style="standard",
        source="https://www.wuhan.gov.cn/zwgk/tzgg/202607/t20260713_2820486.shtml",
    ),
    dict(
        city="大同",
        name="云冈石窟",
        aliases=["云冈石窟景区"],
        group="datong-yungang",
        minutes=180,
        style="half_day",
        source="https://www.dt.gov.cn/dt12345/rxdt1/202604/29b73c0aa08148e3baca536eb7166bb9.shtml",
    ),
    dict(
        city="广州",
        name="广州塔",
        aliases=["广州塔景区"],
        group="guangzhou-tower",
        minutes=120,
        style="standard",
        source="https://www.cantontower.com/?lang=zh",
    ),
    dict(
        city="北京",
        name="故宫博物院",
        aliases=["故宫", "故宫博物院景区"],
        group="beijing-palace",
        minutes=240,
        style="half_day",
        source="https://www.dpm.org.cn/Visit.html",
    ),
    dict(
        city="北京",
        name="八达岭长城",
        aliases=["八达岭长城景区", "长城"],
        group="beijing-great-wall",
        minutes=240,
        style="full_day",
        source="https://www.badaling.cn/",
    ),
]

# Curated equivalent experiences, not containment of all POIs within the old city.
EXPERIENCES = [
    dict(
        city="丽江",
        name="玉龙雪山国家级风景名胜区-玉液湖",
        aliases=["玉液湖", "蓝月谷", "玉龙雪山-蓝月谷"],
        group="lijiang-snow-mountain",
        source="https://yn.yunnan.cn/system/2019/06/26/030308776.shtml",
    ),
    dict(
        city="丽江",
        name="玉龙雪山观景湖",
        aliases=[],
        group="lijiang-snow-mountain",
        source="https://www.amap.com/place/B0K6DS8TXV",
    ),
    dict(
        city="丽江",
        name="玉龙雪山冰川博物馆",
        aliases=[],
        group="lijiang-snow-mountain",
        source="https://yndaily.yunnan.cn/attachment/202402/24/2ef02912-382a-4e31-9f39-619a61277b07.pdf",
    ),
    dict(
        city="北京",
        name="慕田峪长城",
        aliases=["慕田峪长城景区"],
        group="beijing-great-wall",
        landmark=True,
        minutes=240,
        style="full_day",
        source="https://www.beijing.gov.cn/renwen/rwzyd/lyjq/5A/mtycc/202210/t20221018_2838408.html",
    ),
    dict(
        city="大同",
        name="大同古城墙",
        aliases=[
            "大同古城",
            "大同古城南城墙",
            "大同南城墙",
            "大同古城东城墙",
            "大同古城-和阳门",
            "城墙带状公园-大同东城墙",
            "大同古城城墙外带状公园",
        ],
        group="datong-city-wall",
        source="https://www.dt.gov.cn/dtszf/stdt/201811/cbe3380bd8014f1cb4979371687dee29.shtml",
    ),
]


def name_key(name):
    return re.sub(r"[\s·•()（）\[\]【】_-]+", "", name).casefold()


def city_landmarks(city):
    return [item for item in LANDMARKS if item["city"] == city.removesuffix("市")]


def experience(city, name):
    city = city.removesuffix("市")
    key = name_key(name)
    return next(
        (
            item
            for item in LANDMARKS + EXPERIENCES
            if item["city"] == city
            and key in {name_key(n) for n in [item["name"], *item["aliases"]]}
        ),
        None,
    )


def same_experience(city, left, right):
    a, b = experience(city, left), experience(city, right)
    return name_key(left) == name_key(right) or bool(a and b and a["group"] == b["group"])


def metadata(city, name):
    if city.removesuffix("市") == "北京" and name == "长城":
        return {}
    item = experience(city, name)
    if not item:
        return {}
    return {
        "is_landmark": item in LANDMARKS or item.get("landmark", False),
        "experience_group": item["group"],
        "experience_aliases": [
            name
            for member in LANDMARKS + EXPERIENCES
            if member["group"] == item["group"]
            for name in [member["name"], *member["aliases"]]
        ],
        "recommended_minutes": item.get("minutes", 90),
        "visit_style": item.get("style", "standard"),
        "duration_basis": "planning_estimate",
        "identity_source": item["source"],
    }


def discovery_queries(city, interests=(), must_visit=()):
    # All three query families run before reducing the candidate pool.
    return list(
        dict.fromkeys(
            [
                *must_visit[:8],
                *(item["name"] for item in city_landmarks(city)),
                f"{city}城市地标",
                f"{city}必游景点",
                f"{city}5A景区",
                *(
                    f"{city}{term}"
                    for interest in interests[:3]
                    for term in {
                        "历史文化": ("历史文化景点", "博物馆"),
                        "history": ("历史文化景点", "博物馆"),
                        "自然风光": ("自然风光", "公园"),
                        "nature": ("自然风光", "公园"),
                        "美食": ("特色街区", "美食街"),
                        "food": ("特色街区", "美食街"),
                        "购物": ("特色街区",),
                        "shopping": ("特色街区",),
                        "艺术": ("美术馆", "艺术馆"),
                        "art": ("美术馆", "艺术馆"),
                        "休闲": ("休闲景点", "公园"),
                        "leisure": ("休闲景点", "公园"),
                    }.get(interest, (interest,))
                ),
            ]
        )
    )
