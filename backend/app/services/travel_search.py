"""Bounded, read-only MCP searches with shared cache and paid-call accounting."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from redis import Redis

from ..config import Settings
from ..domain.travel_models import TravelOffer, TravelSearchRequest, TravelSearchResponse
from .task_events import redis_url

SOURCES = {
    "train": ("12306（经 12306 MCP 查询）", "https://www.12306.cn/", "12306.cn"),
    "hotel": ("RollingGo", "https://mcp.rollinggo.cn/mcp", "mcp.rollinggo.cn"),
    "flight": ("飞常准", "https://mcp.variflight.com/", "mcp.variflight.com"),
}
RESERVE = """
local n = tonumber(redis.call('GET', KEYS[1]) or '0')
if n >= tonumber(ARGV[1]) then return 0 end
redis.call('INCR', KEYS[1])
return 1
"""


def capabilities(settings: Settings) -> dict:
    return {
        "train": {
            "enabled": settings.travel_train_enabled and not settings.demo_mode,
            "paid": False,
        },
        "hotel": {
            "enabled": settings.travel_hotel_enabled
            and bool(settings.rollinggo_api_key.get_secret_value())
            and not settings.demo_mode,
            "paid": False,
        },
        "flight": {
            "enabled": settings.travel_flight_enabled
            and bool(settings.variflight_api_key.get_secret_value())
            and bool(settings.api_access_code.get_secret_value())
            and settings.travel_flight_call_limit > 0
            and not settings.demo_mode,
            "paid": True,
        },
    }


def response(query: TravelSearchRequest, status: str, message: str, **kwargs):
    title, url, domain = SOURCES[query.provider]
    return TravelSearchResponse(
        provider=query.provider,
        status=status,
        message=message,
        source_title=title,
        source_url=url,
        source_domain=domain,
        trust_level="unknown" if query.provider == "train" else "major_platform",
        query=query.model_copy(update={"confirm_paid": False}),
        **kwargs,
    )


def arguments(query: TravelSearchRequest) -> dict:
    if query.provider == "train":
        return {
            "date": query.date.isoformat(),
            "fromStation": query.origin,
            "toStation": query.destination,
            "trainFilterFlags": "GD" if query.high_speed_only else "",
            "limitedNum": 5,
            "sortFlag": "startTime",
            "format": "json",
        }
    if query.provider == "hotel":
        return {
            "originQuery": f"{query.destination} {query.country} 酒店查询",
            "place": f"{query.destination} {query.country}",
            "placeType": "城市",
            "size": 5,
            "checkInParam": {
                "checkInDate": query.date.isoformat(),
                "stayNights": query.nights,
                "adultCount": query.adults,
            },
        }
    return {
        "dep_city": query.origin,
        "arr_city": query.destination,
        "dep_date": query.date.isoformat(),
    }


def run_mcp(query: TravelSearchRequest, settings: Settings):
    return run_readonly_mcp(query.provider, arguments(query), settings)


def run_readonly_mcp(provider: str, tool_arguments: dict, settings: Settings, *, tool=None):
    allowed = {
        "train": {"get-tickets"},
        "hotel": {"searchHotels", "getHotelDetail", "getHotelSearchTags"},
        "flight": {"getFlightPriceByCities"},
    }
    if provider not in allowed or (tool is not None and tool not in allowed[provider]):
        raise ValueError("unsupported_readonly_tool")
    payload = {"provider": provider, "arguments": tool_arguments}
    if tool is not None:
        payload["tool"] = tool
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        in {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "HOME",
            "LANG",
        }
    }
    env.update(
        TRAVEL_MCP_NODE=settings.travel_mcp_node, TRAVEL_MCP_MODULES=settings.travel_mcp_modules
    )
    if provider == "hotel":
        env["ROLLINGGO_API_KEY"] = settings.rollinggo_api_key.get_secret_value()
    elif provider == "flight":
        env["VARIFLIGHT_API_KEY"] = settings.variflight_api_key.get_secret_value()
    bridge = Path(__file__).resolve().parents[2] / "scripts/travel_mcp_bridge.py"
    completed = subprocess.run(
        [settings.travel_mcp_python, str(bridge)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
        env=env,
        check=True,
    )
    # Prevent accidentally forwarding an echoed secret in a third-party field.
    text = completed.stdout
    for key in (settings.rollinggo_api_key, settings.variflight_api_key):
        if key.get_secret_value():
            text = text.replace(key.get_secret_value(), "[redacted]")
    return json.loads(text)


def money(value) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return round(number, 2) if math.isfinite(number) and number >= 0 else None
    except (ValueError, TypeError):
        return None


def text(value, maximum=180) -> str:
    return str(value)[:maximum] if isinstance(value, (str, int, float)) else ""


def flight_time(value) -> str:
    try:
        return datetime.fromtimestamp(float(value), ZoneInfo("Asia/Shanghai")).strftime(
            "%Y-%m-%d %H:%M"
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def normalize(query: TravelSearchRequest, payload) -> list[TravelOffer]:
    offers = []
    if query.provider == "train":
        if not isinstance(payload, list):
            raise ValueError("invalid_train_response")
        for row in payload[:5]:
            if not isinstance(row, dict) or row.get("start_date") != query.date.isoformat():
                continue
            for fare in row.get("prices", [])[:5]:
                if not isinstance(fare, dict):
                    continue
                offers.append(
                    TravelOffer(
                        offer_id=f"{row.get('start_train_code')}-{fare.get('short')}",
                        title=text(row.get("start_train_code")),
                        subtitle=f"{text(row.get('from_station'))} → {text(row.get('to_station'))}",
                        departure=f"{row['start_date']} {text(row.get('start_time'))}",
                        arrival=f"{text(row.get('arrive_date'))} {text(row.get('arrive_time'))}",
                        price=money(fare.get("price")),
                        price_basis="per_person",
                        fare_label=text(fare.get("seat_name")),
                        availability=text(fare.get("num")),
                        booking_url="https://www.12306.cn/",
                        notes=["余票为查询时快照，以 12306 下单页面为准。"],
                    )
                )
    elif query.provider == "hotel":
        if (
            not isinstance(payload, dict)
            or payload.get("success") is not True
            or not isinstance(payload.get("hotelInformationList"), list)
        ):
            raise ValueError("invalid_hotel_response")
        for row in payload["hotelInformationList"][:5]:
            if not isinstance(row, dict) or not row.get("name"):
                continue
            price = row.get("price") if isinstance(row.get("price"), dict) else {}
            offers.append(
                TravelOffer(
                    offer_id=text(row.get("hotelId")),
                    title=text(row["name"]),
                    subtitle=text(row.get("address")),
                    price=money(price.get("lowestPrice"))
                    if price.get("hasPrice") is True
                    else None,
                    currency=text(price.get("currency") or "CNY", 8),
                    price_basis="stay_total",
                    fare_label=f"1 间房 · {query.adults} 位成人 · {query.nights} 晚总价",
                    notes=["酒店展示起价；房型、餐食、税费及取消政策需在预订平台再次核实。"],
                )
            )
    else:
        if (
            not isinstance(payload, dict)
            or str(payload.get("code")) != "200"
            or not isinstance(payload.get("data"), list)
        ):
            raise ValueError("invalid_flight_response")
        for row in payload["data"]:
            if not isinstance(row, dict) or (
                row.get("depcitycode"),
                row.get("arrcitycode"),
                row.get("depdate"),
            ) != (query.origin, query.destination, query.date.isoformat()):
                continue
            cabins = [
                fare
                for fare in row.get("cabins", [])
                if isinstance(fare, dict)
                and money(fare.get("price")) is not None
                and str(fare.get("seatnum")) not in {"0", "无"}
            ]
            if not cabins:
                continue
            fare = min(cabins, key=lambda item: money(item["price"]))
            offers.append(
                TravelOffer(
                    offer_id=f"{text(row.get('flightno'))}-{text(fare.get('cabincode'))}",
                    title=text(row.get("flightno")),
                    subtitle=f"{text(row.get('depaptcname'))} ({text(row.get('flightdepcode'))}) → {text(row.get('arraptcname'))} ({text(row.get('flightarrcode'))})",
                    departure=flight_time(row.get("flightdeptimeplandate")),
                    arrival=flight_time(row.get("flightarrtimeplandate")),
                    price=money(fare["price"]),
                    price_basis="per_person",
                    fare_label=text(fare.get("classname")),
                    notes=[
                        "供应商舱位票价，非含税总价；税费、行李额和退改政策需另行核实。",
                        "时刻以北京时间显示，航班与价格以出票时为准。",
                    ],
                )
            )
        offers.sort(key=lambda item: item.price)
    return offers[: 25 if query.provider == "train" else 5]


def search(query: TravelSearchRequest, settings: Settings, client=None) -> TravelSearchResponse:
    if not capabilities(settings)[query.provider]["enabled"]:
        return response(query, "disabled", "此查询服务尚未启用或未完成配置。")
    if query.provider == "flight" and not query.confirm_paid:
        return response(query, "disabled", "请先确认本次查询可能消耗飞常准余额。")
    credential = {
        "train": "public",
        "hotel": settings.rollinggo_api_key.get_secret_value(),
        "flight": settings.variflight_api_key.get_secret_value(),
    }[query.provider]
    account = hashlib.sha256(credential.encode()).hexdigest()[:24]
    digest = hashlib.sha256(json.dumps(arguments(query), sort_keys=True).encode()).hexdigest()
    cache_key = f"journeyops:travel:v1:{query.provider}:{account}:{digest}"
    owns_client = client is None
    store = client or Redis.from_url(
        redis_url(), decode_responses=True, socket_timeout=3, socket_connect_timeout=3
    )
    try:
        cached = store.get(cache_key)
        if cached:
            result = TravelSearchResponse.model_validate_json(cached)
            result.cached = True
            return result
        # Keep the short lease even after failure to suppress ambiguous retries/duplicate spend.
        if not store.set(cache_key + ":lock", "1", nx=True, ex=60):
            return response(query, "busy", "相同查询正在处理或刚刚失败，请一分钟后重试。")
        if query.provider == "flight":
            quota_key = f"journeyops:travel:flight:calls:{account}"
            if not store.eval(RESERVE, 1, quota_key, settings.travel_flight_call_limit):
                return response(query, "budget_exhausted", "已达到管理员设置的飞常准累计查询上限。")
        try:
            offers = normalize(query, run_mcp(query, settings))
        except Exception:
            return response(
                query, "unavailable", "供应商暂未返回可用数据，请稍后查询；原行程不受影响。"
            )
        result = response(
            query,
            "ok" if offers else "empty",
            "查询完成，报价及库存以预订平台为准。" if offers else "没有符合条件的可用结果。",
            offers=offers,
            fetched_at=datetime.now(timezone.utc),
        )
        store.set(cache_key, result.model_dump_json(), ex=300)
        return result
    except Exception:
        # Fail closed when shared accounting is unavailable; never fall back to an unmetered call.
        return response(query, "unavailable", "查询缓存或额度服务暂不可用，请稍后重试。")
    finally:
        if owns_client:
            store.close()
