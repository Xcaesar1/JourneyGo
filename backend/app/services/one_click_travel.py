"""Bounded round-trip planning from durable supplier and map evidence."""

import hashlib
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from math import asin, cos, radians, sin, sqrt
from statistics import median
from unicodedata import normalize
from zoneinfo import ZoneInfo

import httpx
from redis import Redis

from ..domain.travel_models import TravelSearchRequest
from ..domain.trip_models import (
    AttractionV2,
    BudgetV2,
    DayPlanV2,
    HotelV2,
    LocationV2,
    MealV2,
    RouteEstimateV2,
    ScheduleItemV2,
    TripPlanV2,
)
from .attraction_discovery import rank_amap_pois
from .hotel_detail import detail_arguments, inspect_detail
from .hotel_pricing import amount, estimate_stay
from .meal_pricing import meal_reference
from .task_events import redis_url
from .travel_ledger import PlanningInputRequired, QueryLedger, QueryReuseUnavailable
from .travel_place_selection import PlaceSelection, select_places, selection_notices
from .travel_search import RESERVE, arguments, capabilities, flight_time, run_readonly_mcp

# Only codes already verified in this integration are enabled. Never guess airport codes.
# Xi'an city code (not airport XIY): CAAC P020160122452786310808.pdf.
FLIGHT_CITIES = {"北京": "BJS", "上海": "SHA", "广州": "CAN", "合肥": "HFE", "西安": "SIA"}
TIERS = {"economy": (0, 3), "business": (3, 4.5), "premium": (4.5, 5)}


def preflight(request, settings):
    if request.planning_mode != "one_click":
        return
    if not settings.one_click_travel_enabled or settings.planner_engine != "journey_graph":
        raise ValueError("一键完整规划尚未启用。")
    enabled = capabilities(settings)
    if not enabled[request.intercity_mode]["enabled"] or not enabled["hotel"]["enabled"]:
        raise ValueError("所选交通或酒店查询尚未启用。")
    if not settings.vite_amap_web_key:
        raise ValueError("高德地点查询尚未配置，暂不能生成可导航行程。")
    if not all(
        (
            settings.openai_api_key.strip(),
            settings.openai_base_url.strip(),
            settings.openai_model.strip(),
        )
    ):
        raise ValueError("规划模型尚未配置，暂不能提交交通和酒店查询。")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if request.start_date < today or request.end_date > today + timedelta(days=365):
        raise ValueError("请选择未来一年内的旅行日期。")
    if request.intercity_mode == "train" and request.end_date > today + timedelta(days=14):
        raise ValueError("去程和返程均须在未来 15 天内，请调整日期。")
    if request.intercity_mode == "flight":
        if not request.flight_confirmed:
            raise ValueError("请确认往返航班最多各查询一次，可能消耗余额。")
        if any(
            city.removesuffix("市") not in FLIGHT_CITIES
            for city in [request.origin, request.destinations[0].city]
        ):
            raise ValueError("该城市的航班代码尚未核实，请使用火车高铁或已支持的航班城市。")


def cents(value):
    parsed = amount(value)
    return (
        None
        if parsed is None
        else int((parsed * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    )


def place_name_key(value):
    return "".join(
        character for character in normalize("NFKC", value).casefold() if character.isalnum()
    )


def place_distance_meters(left, right):
    """Return a stable straight-line distance between two verified POIs."""
    left_location = left["location"]
    right_location = right["location"]
    left_latitude = radians(float(left_location["latitude"]))
    right_latitude = radians(float(right_location["latitude"]))
    latitude_delta = right_latitude - left_latitude
    longitude_delta = radians(
        float(right_location["longitude"]) - float(left_location["longitude"])
    )
    value = sin(latitude_delta / 2) ** 2 + (
        cos(left_latitude) * cos(right_latitude) * sin(longitude_delta / 2) ** 2
    )
    return int(12_742_000 * asin(sqrt(min(1.0, value))))


def hotel_location_score(hotel, attractions, restaurants):
    """Prefer hotels near one fixed relevance-ranked reference set."""

    def reference_median(places, limit):
        distances = [place_distance_meters(hotel, place) for place in places[:limit]]
        return int(median(distances)) if distances else 0

    required = [place for place in attractions if place.get("required")]
    required_distance = (
        sum(place_distance_meters(hotel, place) for place in required) // len(required)
        if required
        else 0
    )
    activity_distance = reference_median(attractions, min(10, len(attractions)))
    meal_distance = reference_median(restaurants, min(5, len(restaurants)))
    return required_distance + activity_distance + meal_distance // 2, hotel["cost_cents"]


def replan_quote_revision(thread_id, refresh_token):
    identity = f"{thread_id}:{refresh_token or 'no-explicit-refresh'}"
    return int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16)


def preserve_replan_quote_revisions(request, changes, thread_id):
    preserved = request.model_copy(deep=True)
    revision = replan_quote_revision(thread_id, changes.refresh_token)
    if changes.refresh_travel:
        preserved.quote_revision[changes.refresh_travel] = revision
    if changes.refresh_sources:
        preserved.quote_revision["amap"] = revision
    return preserved


def replan_request(original, changes, revision):
    request = (changes.travel_request or original).model_copy(deep=True)
    if request.planning_mode != "one_click":
        raise ValueError("A one-click trip cannot silently switch planning modes.")
    if changes.budget_total is not None:
        request.budget_total = changes.budget_total
    request.must_visit = list(dict.fromkeys([*request.must_visit, *changes.add_attractions]))
    request.avoid = list(dict.fromkeys([*request.avoid, *changes.remove_attractions]))
    request.must_visit = [p for p in request.must_visit if p not in request.avoid]
    if changes.instruction != "Refresh travel proposal":
        request.free_text_input = "\n".join(
            filter(None, [request.free_text_input, changes.instruction])
        )
        if len(request.free_text_input) > 2000:
            raise ValueError("特殊需求与修改说明合计过长，请精简后再提交。")
    if changes.transport_preferences is not None:
        modes = set(changes.transport_preferences)
        if len(modes) != 1 or not modes <= {"train", "flight"}:
            raise ValueError("一键规划仅支持一种城际交通：train 或 flight。")
        request.intercity_mode = next(iter(modes))
    flight_changed = any(
        getattr(request, name) != getattr(original, name)
        for name in (
            "origin",
            "destinations",
            "start_date",
            "end_date",
            "travelers",
            "intercity_mode",
        )
    )
    if request.intercity_mode == "flight" and (
        flight_changed or changes.refresh_travel == "flight"
    ):
        if not changes.confirm_flight_queries:
            raise ValueError("Changed or refreshed flights require new explicit consent.")
        request.flight_confirmed = True
    elif request.intercity_mode == "flight":
        request.flight_confirmed = original.flight_confirmed
    request.quote_revision = dict(original.quote_revision)
    if changes.refresh_travel:
        request.quote_revision[changes.refresh_travel] = revision
    if changes.refresh_sources:
        request.quote_revision["amap"] = revision
    return request


def available(value, adults):
    if value in ("有", "充足", "A", "9+"):
        return True
    try:
        return not isinstance(value, bool) and int(value) >= adults
    except (TypeError, ValueError):
        return False


def transport_candidates(payload, query):
    candidates = []
    if query.provider == "train":
        rows = payload if isinstance(payload, list) else []
        for row in rows:
            if not isinstance(row, dict) or not str(row.get("start_train_code", "")).startswith(
                ("G", "D")
            ):
                continue
            for fare in row.get("prices", []):
                if not isinstance(fare, dict):
                    continue
                if fare.get("seat_name") != "二等座" or not available(
                    fare.get("num"), query.adults
                ):
                    continue
                candidates.append(
                    {
                        "number": row.get("start_train_code"),
                        "departure": f"{row.get('start_date')} {row.get('start_time')}",
                        "arrival": f"{row.get('arrive_date')} {row.get('arrive_time')}",
                        "from_name": row.get("from_station"),
                        "to_name": row.get("to_station"),
                        "price_cents": cents(fare.get("price")),
                        "seat": "二等座",
                    }
                )
    elif isinstance(payload, dict) and str(payload.get("code")) == "200":
        for row in payload.get("data", []):
            if not isinstance(row, dict):
                continue
            if (row.get("depcitycode"), row.get("arrcitycode"), row.get("depdate")) != (
                query.origin,
                query.destination,
                query.date.isoformat(),
            ):
                continue
            if row.get("stopcities") or row.get("stopover") or row.get("transfer"):
                continue
            for fare in row.get("cabins", []):
                if not isinstance(fare, dict):
                    continue
                if fare.get("classname") != "经济舱" or not available(
                    fare.get("seatnum"), query.adults
                ):
                    continue
                candidates.append(
                    {
                        "number": row.get("flightno"),
                        "departure": flight_time(row.get("flightdeptimeplandate")),
                        "arrival": flight_time(row.get("flightarrtimeplandate")),
                        "from_name": row.get("depaptcname"),
                        "to_name": row.get("arraptcname"),
                        "price_cents": cents(fare.get("price")),
                        "seat": "经济舱",
                    }
                )
    valid = []
    for item in candidates:
        try:
            departure = datetime.fromisoformat(item["departure"])
            arrival = datetime.fromisoformat(item["arrival"])
            if not (departure.date() == arrival.date() == query.date and arrival > departure):
                continue
            if departure <= datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None):
                continue
            if (
                item["price_cents"] is None
                or not item["from_name"]
                or not item["to_name"]
                or not item.get("number")
            ):
                continue
            item.update(
                departure=departure.isoformat(),
                arrival=arrival.isoformat(),
                provider=query.provider,
            )
            valid.append(item)
        except (ValueError, TypeError):
            continue
    return valid


class OneClickPlanner:
    def __init__(
        self,
        trip_id,
        request,
        settings,
        *,
        ledger=None,
        supplier=None,
        maps=None,
        progress=None,
        selector=None,
    ):
        self.request, self.settings = request, settings
        self.ledger = ledger or QueryLedger(trip_id, request)
        self.supplier = supplier or self._supplier
        self.maps = maps or self._maps
        self.progress = progress or (lambda stage: None)
        self.selector = selector or (lambda context: select_places(self.settings, context))
        self.selection_notes = ""
        self.candidate_notes = []
        self.planning_notices = []

    def discover_attractions(self, city):
        r = self.request
        places = []
        for name in r.must_visit:
            candidate = self.pois(city, name, "110000", exact=True)[0]
            places.append({**candidate, "required": True})
        interests = [
            i
            for i in r.interests[:3]
            if not any(word in i.casefold() for word in ("美食", "餐饮", "food", "dining"))
        ]
        primary = " ".join(interests) or "景点"
        queries = list(dict.fromkeys([primary, "历史古迹", "景点"]))
        reuse_only = r.quote_revision.get("model", 0) > 0 and not r.quote_revision.get("amap", 0)
        if reuse_only:
            # Older paused tasks used a mixed-interest key; try cached keys only.
            queries = list(
                dict.fromkeys([primary, " ".join(r.interests[:3]) or "景点", "历史古迹", "景点"])
            )
        unique = {p["poi_id"]: p for p in places}
        for keyword in queries:
            try:
                candidates = self.pois(city, keyword, "110000")
            except QueryReuseUnavailable:
                continue
            except PlanningInputRequired as exc:
                if exc.payload["code"] != "poi_unmatched":
                    raise
                continue
            for place in candidates:
                if not any(name in place["name"] for name in r.avoid):
                    unique.setdefault(place["poi_id"], place)
            if len(unique) >= min(12, max(4, r.travel_days * 2)):
                break
        if not unique:
            raise PlanningInputRequired(
                "no_places", "没有可核实的景点，请调整偏好或明确刷新地点查询。", provider="amap"
            )
        if len(unique) < min(12, max(4, r.travel_days * 2)):
            self.candidate_notes.append(
                "已核实景点较少，按实际游览时间安排，保留休息时间，不重复或虚构景点。"
            )
        return list(unique.values())

    def _supplier(self, provider, tool, args):
        if provider == "flight":
            account = hashlib.sha256(
                self.settings.variflight_api_key.get_secret_value().encode()
            ).hexdigest()[:24]
            with Redis.from_url(redis_url(), decode_responses=True, socket_timeout=3) as store:
                if not store.eval(
                    RESERVE,
                    1,
                    f"journeyops:travel:flight:calls:{account}",
                    self.settings.travel_flight_call_limit,
                ):
                    raise PlanningInputRequired(
                        "flight_budget_exhausted",
                        "已达到飞常准累计调用上限，需要管理员明确批准新额度。",
                        provider="flight",
                    )
        return run_readonly_mcp(provider, args, self.settings, tool=tool)

    def query(self, provider, scope, tool, args):
        return self.ledger.execute(
            provider, scope, {"tool": tool, **args}, lambda: self.supplier(provider, tool, args)
        )

    def _maps(self, city, keyword, kind):
        if not self.settings.vite_amap_web_key:
            raise ValueError("map_not_configured")
        with httpx.Client(timeout=20) as client:
            response = client.get(
                "https://restapi.amap.com/v5/place/text",
                params={
                    "key": self.settings.vite_amap_web_key,
                    "keywords": keyword,
                    "region": city,
                    "city_limit": "false" if kind == "150100" else "true",
                    "types": kind,
                    "page_size": 25,
                    "show_fields": "business,photos",
                },
            )
            response.raise_for_status()
            return {**response.json(), "fetched_at": datetime.now(timezone.utc).isoformat()}

    def pois(self, city, keyword, kind, *, exact=False):
        raw = self.ledger.execute(
            "amap",
            "poi",
            {"city": city, "keyword": keyword, "kind": kind},
            lambda: self.maps(city, keyword, kind),
        )
        ranked = {}
        rank_position = {}
        if kind == "110000":
            ranked_places = rank_amap_pois(
                raw,
                city,
                interests=self.request.interests,
                must_visit=self.request.must_visit,
                avoid=self.request.avoid,
            )
            ranked = {p.poi_id: p for p in ranked_places}
            rank_position = {p.poi_id: index for index, p in enumerate(ranked_places)}
        results = []
        keyword_key = place_name_key(keyword)
        for provider_index, row in enumerate(
            raw.get("pois", []) if str(raw.get("status")) == "1" else []
        ):
            try:
                lon, lat = map(float, row["location"].split(","))
                if not row["id"].startswith("B") or not 73 <= lon <= 136 or not 18 <= lat <= 54:
                    continue
                adcode = str(row.get("adcode", ""))
                if (
                    len(adcode) != 6
                    or not adcode.isdigit()
                    or adcode[:2]
                    not in {
                        "11",
                        "12",
                        "13",
                        "14",
                        "15",
                        "21",
                        "22",
                        "23",
                        "31",
                        "32",
                        "33",
                        "34",
                        "35",
                        "36",
                        "37",
                        "41",
                        "42",
                        "43",
                        "44",
                        "45",
                        "46",
                        "50",
                        "51",
                        "52",
                        "53",
                        "54",
                        "61",
                        "62",
                        "63",
                        "64",
                        "65",
                    }
                ):
                    continue
                name = row["name"]
                if kind == "110000" and row["id"] not in ranked:
                    continue
                if (
                    kind != "150100"
                    and row.get("cityname")
                    and row["cityname"].removesuffix("市") != city.removesuffix("市")
                ):
                    continue
                name_key = place_name_key(name)
                if exact and keyword_key not in name_key and name_key not in keyword_key:
                    continue
                results.append(
                    {
                        "name": name,
                        "poi_id": row["id"],
                        "address": row.get("address") or "",
                        "location": {"longitude": lon, "latitude": lat},
                        "business": row.get("business") or {},
                        "fetched_at": raw.get("fetched_at"),
                        "image": ranked[row["id"]].image.model_dump()
                        if row["id"] in ranked
                        else {},
                        "_provider_index": provider_index,
                    }
                )
            except (ValueError, TypeError, KeyError):
                continue
        if not results:
            raise PlanningInputRequired(
                "poi_unmatched", "无法核实地点，请调整目的地或偏好。", provider="amap"
            )
        results.sort(
            key=lambda place: (
                0 if exact and place_name_key(place["name"]) == keyword_key else 1 if exact else 0,
                rank_position.get(place["poi_id"], len(rank_position)),
                place["_provider_index"],
            )
        )
        for place in results:
            place.pop("_provider_index", None)
        return results

    def run(self):
        r = self.request
        preflight(r, self.settings)
        city = r.destinations[0].city
        self.progress("query_transport")
        legs = []
        for scope, origin, destination, day in [
            ("outbound", r.origin, city, r.start_date),
            ("return", city, r.origin, r.end_date),
        ]:
            if r.intercity_mode == "flight":
                origin, destination = [
                    FLIGHT_CITIES[x.removesuffix("市")] for x in (origin, destination)
                ]
            query = TravelSearchRequest(
                provider=r.intercity_mode,
                origin=origin,
                destination=destination,
                date=day,
                adults=r.travelers,
                confirm_paid=r.flight_confirmed,
            )
            args = arguments(query)
            if r.intercity_mode == "train":
                args["limitedNum"] = 30
            payload = self.query(
                r.intercity_mode,
                scope,
                "get-tickets" if r.intercity_mode == "train" else "getFlightPriceByCities",
                args,
            )
            offers = transport_candidates(payload, query)
            if not offers:
                raise PlanningInputRequired(
                    "no_transport",
                    "没有当天直达、余票和价格完整的往返方案，请调整日期。",
                    provider=r.intercity_mode,
                )

            # Prefer usable destination time while keeping ticket price dominant.
            def score(item):
                time = datetime.fromisoformat(
                    item["arrival"] if scope == "outbound" else item["departure"]
                )
                minutes = time.hour * 60 + time.minute
                return (
                    item["price_cents"] * r.travelers
                    + (minutes if scope == "outbound" else 1440 - minutes) * 10
                )

            legs.append(sorted(offers, key=score))
        candidates = [
            (a, b)
            for a in legs[0]
            for b in legs[1]
            if datetime.fromisoformat(a["departure"]).hour
            >= (2 if r.intercity_mode == "train" else 3)
        ]

        def pair_score(pair):
            arrival = datetime.fromisoformat(pair[0]["arrival"])
            departure = datetime.fromisoformat(pair[1]["departure"])
            return (
                sum(x["price_cents"] for x in pair) * r.travelers
                + (
                    arrival.hour * 60
                    + arrival.minute
                    + 1440
                    - departure.hour * 60
                    - departure.minute
                )
                * 10
            )

        combinations = sorted(candidates, key=pair_score)
        if not combinations:
            raise PlanningInputRequired(
                "no_transport",
                "去程无法在所选日期内预留接驳和候车时间，请调整日期。",
                provider=r.intercity_mode,
            )
        outbound, inbound = combinations[0]
        known_cents = min(
            (a["price_cents"] + b["price_cents"]) * r.travelers for a, b in combinations
        )
        hotel_allowance = cents(r.budget_total) - known_cents - 21000 * r.travel_days * r.travelers
        if hotel_allowance <= 0:
            raise PlanningInputRequired(
                "over_budget", "往返交通和基本餐饮接驳估算已超预算，请提高预算或调整日期。"
            )
        terminal_type = "150200" if r.intercity_mode == "train" else "150100"
        self.progress("query_hotel")
        hotel_query = TravelSearchRequest(
            provider="hotel",
            destination=city,
            date=r.start_date,
            nights=r.travel_days - 1,
            adults=r.travelers,
        )
        args = arguments(hotel_query)
        args.update(
            size=10,
            filterOptions={"starRatings": list(TIERS[r.hotel_tier])},
            originQuery=f"{city} {r.hotel_tier} 酒店 1间房 {r.travelers}成人",
            hotelTags={
                "maxPricePerNight": float(Decimal(hotel_allowance) / 100 / hotel_query.nights)
            },
        )
        found = self.query("hotel", "search", "searchHotels", args)
        if not isinstance(found, dict) or found.get("success") is not True:
            raise PlanningInputRequired(
                "hotel_unavailable",
                "酒店查询未返回可用结果，请调整条件或更新报价。",
                provider="hotel",
            )
        low, high = TIERS[r.hotel_tier]
        hotels = [
            h
            for h in found.get("hotelInformationList", [])
            if isinstance(h, dict)
            and type(h.get("hotelId")) is int
            and h["hotelId"] > 0
            and isinstance(h.get("name"), str)
            and h["name"].strip()
            and amount(h.get("starRating")) is not None
            and low <= float(h["starRating"]) <= high
        ]
        hotels.sort(key=lambda h: amount(h.get("price", {}).get("lowestPrice")) or Decimal("1e9"))
        self.progress("plan_places")
        attractions = self.discover_attractions(city)
        attractions = [p for p in attractions if not any(name in p["name"] for name in r.avoid)]
        if not attractions:
            raise PlanningInputRequired(
                "no_places", "没有满足偏好的景点，请调整偏好。", provider="amap"
            )
        restaurants = self.pois(city, "当地美食", "050100")
        mapped_hotels = []
        for hotel in hotels[:10]:
            list_total = estimate_stay(
                hotel.get("price", {}).get("lowestPrice"), hotel_query.nights
            )
            list_cost = cents(list_total)
            if list_cost is not None and list_cost > hotel_allowance:
                continue
            try:
                poi = self.pois(city, hotel["name"], "100100", exact=True)[0]
            except PlanningInputRequired:
                continue
            provisional = {**poi, "cost_cents": list_cost or hotel_allowance}
            mapped_hotels.append(
                (hotel_location_score(provisional, attractions, restaurants), hotel, poi)
            )
        mapped_hotels.sort(key=lambda item: item[0])
        hotel_candidates = []
        for _score, hotel, poi in mapped_hotels[:3]:
            detail = self.query(
                "hotel", "detail", "getHotelDetail", detail_arguments(hotel_query, hotel["hotelId"])
            )
            evidence = inspect_detail(hotel_query, hotel["hotelId"], detail)
            list_price = hotel.get("price", {})
            if (
                evidence.status != "estimated"
                and evidence.rooms
                and list_price.get("hasPrice") is True
                and list_price.get("currency") == "CNY"
            ):
                fallback_total = estimate_stay(list_price.get("lowestPrice"), hotel_query.nights)
                if fallback_total is not None:
                    evidence.status = "estimated"
                    evidence.estimated_stay_total = fallback_total
                    evidence.selected_rate_plan_id = evidence.rooms[0].rate_plan_id
                    evidence.pricing_note = "房型已匹配，价格按酒店列表首夜参考价 × 晚数估算，不是该房型确定报价；税费待核实。"
            if evidence.status != "estimated":
                continue
            cost = cents(evidence.estimated_stay_total)
            if cost is None or cost > hotel_allowance:
                continue
            room = next(
                x for x in evidence.rooms if x.rate_plan_id == evidence.selected_rate_plan_id
            )
            hotel_candidates.append(
                {
                    **poi,
                    "hotel_id": hotel["hotelId"],
                    "room_name": room.room_name,
                    "rate_plan_id": room.rate_plan_id,
                    "cost_cents": cost,
                    "nights": hotel_query.nights,
                    "check_in": evidence.check_in,
                    "check_out": evidence.check_out,
                    "adults": r.travelers,
                    "rooms": 1,
                    "pricing_note": evidence.pricing_note,
                }
            )
        if not hotel_candidates:
            raise PlanningInputRequired(
                "no_hotel",
                "没有可核实人数、房型和参考价的同档酒店，请调整日期或住宿偏好。",
                provider="hotel",
            )
        ranked_hotels = sorted(
            hotel_candidates,
            key=lambda hotel: hotel_location_score(hotel, attractions, restaurants),
        )
        failure = None
        failed_hotel_codes = {}
        viable = None
        for hotel_index, hotel in enumerate(ranked_hotels):
            hotel_failures = []
            for candidate_outbound, candidate_inbound in combinations[:30]:
                try:
                    candidate_outbound["location"] = self.pois(
                        city, candidate_outbound["to_name"], terminal_type, exact=True
                    )[0]
                    candidate_outbound["origin_location"] = self.pois(
                        r.origin,
                        candidate_outbound["from_name"],
                        terminal_type,
                        exact=True,
                    )[0]
                    candidate_inbound["location"] = self.pois(
                        city, candidate_inbound["from_name"], terminal_type, exact=True
                    )[0]
                    total = (
                        candidate_outbound["price_cents"] + candidate_inbound["price_cents"]
                    ) * r.travelers
                    # This probe is deterministic and uses only already verified candidates.
                    probe = self.schedule(
                        candidate_outbound,
                        candidate_inbound,
                        hotel,
                        attractions,
                        restaurants,
                        total,
                    )
                    viable = (
                        hotel_index,
                        hotel,
                        candidate_outbound,
                        candidate_inbound,
                        total,
                    )
                    break
                except PlanningInputRequired as exc:
                    failure = exc
                    hotel_failures.append(exc.payload["code"])
            failed_hotel_codes[hotel["hotel_id"]] = list(dict.fromkeys(hotel_failures))
            if viable is not None:
                break
        if viable is None:
            raise failure or PlanningInputRequired(
                "no_viable_hotel_transport", "没有可同时满足接驳与时间约束的交通和酒店组合。"
            )
        hotel_index, chosen, outbound, inbound, known_cents = viable
        hotel_fallback = None
        if hotel_index:
            preferred = ranked_hotels[0]
            reason_codes = list(
                dict.fromkeys(
                    code
                    for hotel in ranked_hotels[:hotel_index]
                    for code in failed_hotel_codes.get(hotel["hotel_id"], [])
                )
            )
            hotel_fallback = {
                "from_hotel_id": preferred["hotel_id"],
                "from_name": preferred["name"],
                "to_hotel_id": chosen["hotel_id"],
                "to_name": chosen["name"],
                "reason_codes": reason_codes,
            }
        context = {
            "selection_contract_version": 3,
            "activity_windows": probe.travel_summary["activity_windows"],
            "request": r.model_dump(mode="json"),
            "attractions": attractions,
            "restaurants": restaurants,
            "hotel": chosen,
            "transport": [outbound, inbound],
        }
        # Preference-only replanning reuses paid transport but gets its own structured selection.
        selected = PlaceSelection.model_validate(
            self.ledger.execute("model", "place_selection", context, lambda: self.selector(context))
        )
        advisory, blockers = selection_notices(selected, r)
        if blockers:
            raise PlanningInputRequired(
                "requirement_confirmation",
                "需要确认你明确提出的要求：" + "；".join(blockers),
                provider="model",
            )
        attr_by_id = {p["poi_id"]: p for p in attractions}
        meal_by_id = {p["poi_id"]: p for p in restaurants}
        if (
            not set(selected.attraction_ids) <= attr_by_id.keys()
            or not set(selected.restaurant_ids) <= meal_by_id.keys()
            or any(
                p.get("required") and p["poi_id"] not in selected.attraction_ids
                for p in attractions
            )
        ):
            raise PlanningInputRequired("invalid_selection", "规划地点未通过核验，请调整偏好。")
        selected_attractions = set(selected.attraction_ids)
        selected_restaurants = set(selected.restaurant_ids)
        attractions = [
            {**place, "selected": key in selected_attractions} for key, place in attr_by_id.items()
        ]
        restaurants = [
            {**place, "selected": key in selected_restaurants} for key, place in meal_by_id.items()
        ]
        self.selection_notes = " ".join([selected.notes, *self.candidate_notes, *advisory])
        self.planning_notices = [*self.candidate_notes, *advisory]
        if hotel_fallback is not None:
            self.selection_notes += " 首选酒店无法满足每日接驳约束，已改用同批核验的备选酒店。"
        self.progress("check_trip")
        return self.schedule(
            outbound,
            inbound,
            chosen,
            attractions,
            restaurants,
            known_cents,
            hotel_fallback=hotel_fallback,
        )

    def schedule(
        self,
        outbound,
        inbound,
        hotel,
        attractions,
        restaurants,
        known_cents,
        *,
        hotel_fallback=None,
    ):
        r = self.request
        city = r.destinations[0].city
        arrival = datetime.fromisoformat(outbound["arrival"])
        departure = datetime.fromisoformat(inbound["departure"])
        buffer = 60 if r.intercity_mode == "train" else 120
        days, routes, activity_windows = [], [], []

        def transfer(a, b):
            meters = place_distance_meters(a, b)
            return max(20, int(meters * 1.5 / 20000 * 60) + 20)

        def entry(day, title, start, duration, kind="transport", poi=None):
            item_id = f"d{day}-{start:%H%M}-{kind}"
            actual = title.startswith(outbound["number"] + " ") or title.startswith(
                inbound["number"] + " "
            )
            if kind == "transport":
                routes.append(
                    RouteEstimateV2(
                        estimate_id=item_id,
                        origin=city,
                        destination=title,
                        duration_minutes=duration,
                        mode="straight_line",
                        provider=r.intercity_mode if actual else "local-estimate",
                        status="verified" if actual else "estimated",
                        detail="供应商时刻" if actual else "基于地点距离估算，非实时路况",
                    )
                )
            return ScheduleItemV2(
                item_id=item_id,
                item_type=kind,
                title=title,
                start=start,
                end=start + timedelta(minutes=duration),
                duration_minutes=duration,
                route_estimate_id=item_id if kind == "transport" else None,
                reference_name=title if kind != "transport" else None,
                location=LocationV2(**poi["location"]) if poi else None,
            )

        remaining = list(attractions)
        scheduled_restaurant_ids = set()
        scheduled_attraction_count = 0
        meals_cents = local_cents = 0
        for i in range(r.travel_days):
            day = r.start_date + timedelta(days=i)
            start = datetime.combine(day, r.daily_start_time)
            end = datetime.combine(day, r.daily_end_time)
            timeline, day_attractions, meals = [], [], []
            commute_limit = 240 if i in {0, r.travel_days - 1} else 180
            local_minutes = 0
            if i == 0:
                dep = datetime.fromisoformat(outbound["departure"])
                timeline.append(
                    entry(
                        i,
                        "出发城市内接驳（预估60分钟，需按实际出发位置核实）",
                        dep - timedelta(minutes=buffer + 60),
                        60,
                        poi=outbound["origin_location"],
                    )
                )
                local_minutes += 60
                timeline.append(
                    entry(
                        i,
                        "去程候车 / 值机预留",
                        dep - timedelta(minutes=buffer),
                        buffer,
                        "free_time",
                        poi=outbound["origin_location"],
                    )
                )
                timeline.append(
                    entry(
                        i,
                        f"{outbound['number']} {outbound['from_name']} → {outbound['to_name']}",
                        dep,
                        int((arrival - dep).total_seconds() / 60),
                    )
                )
                minutes = transfer(outbound["location"], hotel)
                if (arrival + timedelta(minutes=minutes + 30)).date() != day:
                    raise PlanningInputRequired(
                        "late_arrival", "抵达酒店已跨日，请选择更早到达的交通方案。"
                    )
                timeline.append(entry(i, "到站后接驳至酒店（估算）", arrival, minutes, poi=hotel))
                local_minutes += minutes
                start = max(start, arrival + timedelta(minutes=minutes + 30))
            return_minutes = transfer(hotel, inbound["location"])
            reserved_return_minutes = return_minutes if i == r.travel_days - 1 else 0
            if local_minutes + reserved_return_minutes > commute_limit:
                raise PlanningInputRequired(
                    "local_transfer_excessive",
                    "酒店与交通枢纽距离过远，无法在合理接驳时间内完成行程。",
                )
            if i == r.travel_days - 1:
                end = min(end, departure - timedelta(minutes=buffer + return_minutes + 30))
            activity_windows.append(
                {
                    "date": day.isoformat(),
                    "start": start.isoformat(),
                    "end": max(start, end).isoformat(),
                    "available_minutes": max(0, int((end - start).total_seconds() / 60)),
                    "is_transfer_day": i in {0, r.travel_days - 1},
                }
            )
            current, previous = start, hotel
            for slot in range(3):
                if remaining:
                    feasible = []
                    for poi in remaining:
                        travel = transfer(previous, poi)
                        return_to_hotel = transfer(poi, hotel)
                        if (
                            local_minutes + travel + return_to_hotel + reserved_return_minutes
                            <= commute_limit
                            and current + timedelta(minutes=travel + 90 + return_to_hotel) <= end
                        ):
                            feasible.append(
                                (
                                    not poi.get("required"),
                                    not poi.get("selected"),
                                    travel,
                                    poi["name"],
                                    poi,
                                )
                            )
                    if feasible:
                        *_, travel, _name, poi = min(feasible, key=lambda item: item[:-1])
                        remaining.remove(poi)
                        timeline.append(entry(i, "市内接驳（估算）", current, travel, poi=poi))
                        local_minutes += travel
                        current += timedelta(minutes=travel)
                        timeline.append(entry(i, poi["name"], current, 90, "attraction", poi))
                        current += timedelta(minutes=90)
                        day_attractions.append(
                            AttractionV2(
                                name=poi["name"],
                                address=poi["address"],
                                poi_id=poi["poi_id"],
                                location=LocationV2(**poi["location"]),
                                visit_duration=90,
                                image_url=poi.get("image", {}).get("url", ""),
                                image_source=poi.get("image", {}).get("source", ""),
                                image_source_page=poi.get("image", {}).get("source_page", ""),
                                image_attribution=poi.get("image", {}).get("attribution", ""),
                                description="营业时间、门票与预约要求待核实。",
                            )
                        )
                        scheduled_attraction_count += 1
                        previous = poi
                options = [
                    p for p in restaurants if p["poi_id"] not in {meal.poi_id for meal in meals}
                ] or restaurants
                feasible_meals = []
                for restaurant in options:
                    travel = transfer(previous, restaurant)
                    return_to_hotel = transfer(restaurant, hotel)
                    meal_start = current + timedelta(minutes=travel)
                    meal_type = (
                        "breakfast"
                        if meal_start.hour < 11
                        else "lunch"
                        if meal_start.hour < 16
                        else "dinner"
                    )
                    served = {meal.type for meal in meals}
                    if meal_type in served:
                        meal_type = "lunch" if meal_type == "breakfast" else "dinner"
                    if meal_type in served:
                        continue
                    earliest_hour = {"breakfast": 7, "lunch": 11, "dinner": 17}[meal_type]
                    meal_start = max(
                        meal_start,
                        datetime.combine(day, r.daily_start_time).replace(
                            hour=earliest_hour, minute=0, second=0
                        ),
                    )
                    if (
                        local_minutes + travel + return_to_hotel + reserved_return_minutes
                        <= commute_limit
                        and meal_start + timedelta(minutes=60 + return_to_hotel) <= end
                    ):
                        feasible_meals.append(
                            (
                                not restaurant.get("selected"),
                                travel,
                                restaurant["name"],
                                restaurant,
                                meal_type,
                                meal_start,
                            )
                        )
                if feasible_meals:
                    (
                        _,
                        travel,
                        _,
                        restaurant,
                        meal_type,
                        meal_start,
                    ) = min(feasible_meals, key=lambda item: item[:3])
                    timeline.append(entry(i, "前往餐厅（估算）", current, travel, poi=restaurant))
                    local_minutes += travel
                    current += timedelta(minutes=travel)
                    if meal_start > current:
                        timeline.append(
                            entry(
                                i,
                                "自由活动 / 休息",
                                current,
                                int((meal_start - current).total_seconds() / 60),
                                "free_time",
                                restaurant,
                            )
                        )
                        current = meal_start
                    timeline.append(entry(i, restaurant["name"], current, 60, "meal", restaurant))
                    current += timedelta(minutes=60)
                    meals.append(
                        MealV2(
                            type=meal_type,
                            name=restaurant["name"],
                            address=restaurant["address"],
                            location=LocationV2(**restaurant["location"]),
                            poi_id=restaurant["poi_id"],
                            price_reference=meal_reference(restaurant),
                            description="实际消费以店内为准，营业时间待核实。",
                        )
                    )
                    scheduled_restaurant_ids.add(restaurant["poi_id"])
                    previous = restaurant
            if previous != hotel:
                minutes = transfer(previous, hotel)
                timeline.append(entry(i, "返回酒店（估算）", current, minutes, poi=hotel))
                local_minutes += minutes
            if i == r.travel_days - 1:
                station_start = departure - timedelta(minutes=buffer + return_minutes)
                if station_start.date() != day:
                    raise PlanningInputRequired(
                        "early_return", "返程接驳需要前一天出发，请调整返程日期或交通方案。"
                    )
                timeline.append(
                    entry(
                        i,
                        "酒店至返程枢纽（估算）",
                        station_start,
                        return_minutes,
                        poi=inbound["location"],
                    )
                )
                local_minutes += return_minutes
                timeline.append(
                    entry(
                        i,
                        "候车 / 值机预留",
                        departure - timedelta(minutes=buffer),
                        buffer,
                        "free_time",
                        poi=inbound["location"],
                    )
                )
                arr = datetime.fromisoformat(inbound["arrival"])
                timeline.append(
                    entry(
                        i,
                        f"{inbound['number']} {inbound['from_name']} → {inbound['to_name']}",
                        departure,
                        int((arr - departure).total_seconds() / 60),
                    )
                )
            if local_minutes > commute_limit:
                raise PlanningInputRequired(
                    "local_transfer_excessive",
                    f"第 {i + 1} 天市内接驳超过合理范围，请调整景点或住宿。",
                )
            timeline.sort(key=lambda item: item.start)
            if any(a.end > b.start for a, b in zip(timeline, timeline[1:])):
                raise PlanningInputRequired("time_conflict", "交通接驳时间冲突，请调整出发日期。")
            meals_cents += (
                sum(meal.price_reference.amount_cents for meal in meals if meal.price_reference)
                * r.travelers
            )
            local_cents += 3000 * r.travelers
            days.append(
                DayPlanV2(
                    date=day,
                    day_index=i,
                    city=city,
                    is_transfer_day=i in {0, r.travel_days - 1},
                    description="按实际交通时间与地点距离安排。",
                    transportation="公共交通与必要步行",
                    attractions=day_attractions,
                    meals=meals,
                    timeline=timeline,
                    hotel=HotelV2(
                        name=hotel["name"],
                        address=hotel["address"],
                        poi_id=hotel["poi_id"],
                        location=LocationV2(**hotel["location"]),
                        type=r.hotel_tier,
                        price_range=hotel["pricing_note"],
                    )
                    if i < r.travel_days - 1
                    else None,
                )
            )
        if any(p.get("required") for p in remaining):
            raise PlanningInputRequired(
                "must_visit_unplaced",
                "交通和活动时间内无法安排全部必去景点，请减少景点或调整日期。",
            )
        if scheduled_attraction_count == 0:
            raise PlanningInputRequired(
                "no_schedulable_places",
                "已核实的景点均无法在合理接驳时间内安排，请调整住宿或景点偏好。",
            )
        omitted_places = [p["name"] for p in remaining if p.get("selected")]
        omitted_places.extend(
            p["name"]
            for p in restaurants
            if p.get("selected") and p["poi_id"] not in scheduled_restaurant_ids
        )
        schedule_notes = self.selection_notes
        if omitted_places:
            schedule_notes += (
                " 为控制每日市内接驳和时间冲突，以下偏好候选未排入时间线："
                + "、".join(dict.fromkeys(omitted_places))
                + "。"
            )
        estimated_cents = hotel["cost_cents"] + meals_cents + local_cents
        if known_cents + estimated_cents > cents(r.budget_total):
            raise PlanningInputRequired(
                "over_budget", "同档酒店与原交通方式仍超预算，请提高预算或调整日期、住宿偏好。"
            )
        items = [
            {
                "category": "outbound",
                "status": "quoted",
                "amount_cents": outbound["price_cents"] * r.travelers,
            },
            {
                "category": "return",
                "status": "quoted",
                "amount_cents": inbound["price_cents"] * r.travelers,
            },
            {"category": "hotel", "status": "estimated", "amount_cents": hotel["cost_cents"]},
            {
                "category": "meals",
                "status": "estimated" if meals_cents else "unknown",
                "amount_cents": meals_cents or None,
            },
            {"category": "local_transport", "status": "estimated", "amount_cents": local_cents},
            {"category": "tickets", "status": "unknown", "amount_cents": None},
            {"category": "hotel_taxes", "status": "unknown", "amount_cents": None},
        ]
        if r.intercity_mode == "flight":
            items.append({"category": "flight_taxes", "status": "unknown", "amount_cents": None})
        summary = {
            "outbound": outbound,
            "return": inbound,
            "hotel": hotel,
            "cost_items": items,
            "planning_request": r.model_dump(mode="json"),
            "activity_windows": activity_windows,
            "planning_notices": self.planning_notices,
            "known_cents": known_cents,
            "estimated_cents": estimated_cents,
            "expected_cents": known_cents + estimated_cents,
            "meal_pricing_policy": "amap_reference_only",
            "costs_complete": False,
            "excluded_costs": ["unpriced_meals", "tickets", "hotel_taxes"],
            "currency": "CNY",
            "quotes": [q for q in self.ledger.records if q["provider"] != "model"],
            "booking_status": "not_booked",
            "selection_adjustments": {
                "omitted_preferred_places": list(dict.fromkeys(omitted_places)),
                "reason": "daily_time_and_local_commute_limits" if omitted_places else None,
                "hotel_fallback": hotel_fallback,
            },
        }
        # Legacy integer display is rounded; the authoritative ledger retains exact cents.
        components = [
            round(hotel["cost_cents"] / 100),
            round(meals_cents / 100),
            round(local_cents / 100),
            round(known_cents / 100),
        ]
        return TripPlanV2(
            origin=r.origin,
            city=city,
            cities=[city],
            start_date=r.start_date,
            end_date=r.end_date,
            days=days,
            route_matrix=routes,
            travel_summary=summary,
            overall_suggestions=schedule_notes
            + (
                " 往返交通占比较高，请以每日时间线中的实际可游览时段为准。"
                if sum(w["available_minutes"] >= 180 for w in activity_windows) < r.travel_days
                else ""
            )
            + " 费用为已知报价与参考估算之和，未含待核实项目；确认行程不代表已预订。",
            budget=BudgetV2(
                total_hotels=components[0],
                total_meals=components[1],
                total_transportation=components[2],
                total_inter_city_transport=components[3],
                total=sum(components),
            ),
        )
