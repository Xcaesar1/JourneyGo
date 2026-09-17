"""User-triggered AMap maps from persisted itinerary snapshots."""

import asyncio
import hashlib
import json
import logging
import math
import re
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db.models import TravelQuery, TripReview, TripTask, TripVersion


class _HideMcpCredentials(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        if "mcp.amap.com" in message:
            record.msg = re.sub(r"([?&]key=)[^\s&\"']+", r"\1[REDACTED]", message)
            record.args = ()
        return True


for _logger in ("httpx", "mcp.client.streamable_http"):
    logging.getLogger(_logger).addFilter(_HideMcpCredentials())


def map_lines(plan, day_index=None):
    lines, omitted = [], []
    days = plan.get("days", [])
    if day_index is not None and not 0 <= day_index < len(days):
        raise HTTPException(422, "当天行程不存在。")
    for index, day in enumerate(days):
        if day_index is not None and index != day_index:
            continue
        places = [*day.get("attractions", []), *day.get("meals", [])]
        summary = plan.get("travel_summary") or {}
        if index == 0 and summary.get("outbound", {}).get("location"):
            places.insert(0, summary["outbound"]["location"])
        if day.get("hotel"):
            places.append(day["hotel"])
        if index == len(days) - 1 and summary.get("return", {}).get("location"):
            places.append(summary["return"]["location"])
        by_name = {p.get("name"): p for p in places}
        ordered = []
        for item in sorted(day.get("timeline", []), key=lambda i: i.get("start", "")):
            if item.get("reference_name") in by_name:
                ordered.append(by_name[item["reference_name"]])
        ordered.extend(places)
        points, seen = [], set()
        for place in ordered:
            name, poi_id = place.get("name", ""), place.get("poi_id", "")
            loc = place.get("location") or {}
            lon, lat = loc.get("longitude"), loc.get("latitude")
            valid = all(type(v) in (int, float) and math.isfinite(v) for v in (lon, lat))
            if not (
                valid
                and -180 <= lon <= 180
                and -90 <= lat <= 90
                and (lon != 0 or lat != 0)
                and re.fullmatch(r"B[A-Z0-9]+", poi_id or "")
            ):
                omitted.append(name)
                continue
            if poi_id in seen:
                continue
            seen.add(poi_id)
            points.append({"name": name, "lon": lon, "lat": lat, "poiId": poi_id})
        if points:
            lines.append(
                {"title": f"{day.get('date', '')} 第{index + 1}天", "pointInfoList": points}
            )
    if not lines:
        raise HTTPException(422, "没有可导入的高德地点，请使用单地点导航或复制地址。")
    return lines, list(dict.fromkeys(omitted))


def safe_map_url(value):
    try:
        parsed = urlparse(value)
        return (
            parsed.scheme == "https"
            and parsed.hostname in {"surl.amap.com", "uri.amap.com", "www.amap.com"}
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
        ) or (
            parsed.scheme == "amapuri"
            and parsed.netloc == "workInAmap"
            and parsed.path == "/createWithToken"
        )
    except (ValueError, TypeError):
        return False


async def create_map(key, arguments):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def call():
        async with streamablehttp_client("https://mcp.amap.com/mcp?key=" + quote(key, safe="")) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write) as client:
                await client.initialize()
                result = await client.call_tool("maps_schema_personal_map", arguments)
                if result.isError:
                    raise ValueError("provider_rejected")
                text = "\n".join(block.text for block in result.content if block.type == "text")
                for url in re.findall(r'(?:https://|amapuri://)[^\s<>"\u0027]+', text):
                    url = url.rstrip(").,，。")
                    if safe_map_url(url):
                        return url
                raise ValueError("missing_map_link")

    return await asyncio.wait_for(call(), timeout=30)


def persisted_plan(session, task_id, version, review_id):
    task = session.get(TripTask, task_id)
    if task is None:
        raise HTTPException(404, "行程任务不存在。")
    if review_id:
        review = session.get(TripReview, review_id)
        if not review or review.task_id != task_id or review.status not in {"pending", "applied"}:
            raise HTTPException(409, "草案已更新，请刷新后重试。")
        plan = review.native_payload
    else:
        record = session.scalar(
            select(TripVersion).where(
                TripVersion.trip_id == task.trip_id, TripVersion.version == version
            )
        )
        plan = record.native_payload if record else None
    if not plan:
        raise HTTPException(409, "尚无可导入的行程版本。")
    return task.trip_id, plan


async def export_map(session, settings, task_id, payload, provider=create_map):
    trip_id, plan = persisted_plan(session, task_id, payload.version, payload.review_id)
    lines, omitted = map_lines(plan, payload.day_index)
    arguments = {"orgName": f"JourneyGo {plan.get('city', '')}旅行", "lineList": lines}
    identity = [trip_id, payload.version, payload.review_id, payload.day_index, arguments]
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    row = session.get(TravelQuery, key)
    if row:
        if row.status == "succeeded":
            return row.result
        raise HTTPException(
            409, "地图创建结果尚未确认，为避免重复创建，请稍后联系管理员核对；单地点导航仍可使用。"
        )
    if not settings.amap_personal_map_enabled or not settings.vite_amap_web_key:
        raise HTTPException(
            503, "高德专属地图尚未启用，需先核实账号额度；可继续使用单地点导航或复制地址。"
        )
    row = TravelQuery(
        id=key,
        trip_id=trip_id,
        provider="amap_map",
        scope="personal_map",
        arguments=arguments,
        authorization={"confirmed": True},
        status="dispatching",
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "地图正在创建，请稍后重试。") from None
    try:
        url = await provider(settings.vite_amap_web_key, arguments)
        if not safe_map_url(url):
            raise ValueError("invalid_url")
    except Exception:
        row.status = "uncertain"
        session.commit()
        raise HTTPException(
            502, "未能确认地图创建结果，已停止重复发送；请使用单地点导航。"
        ) from None
    result = {
        "url": url,
        "omitted": omitted,
        "point_count": sum(len(line["pointInfoList"]) for line in lines),
    }
    row.result, row.status = result, "succeeded"
    row.finished_at = datetime.now(timezone.utc)
    session.commit()
    return result
