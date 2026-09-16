"""Deterministic, coordinate-only Open-Meteo MCP collection."""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from ..domain.trip_models import WeatherInfoV2


def gcj02_to_wgs84(lon: float, lat: float) -> tuple[float, float]:
    """Approximate inverse for AMap coordinates; never apply to WGS84 inputs."""
    if not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271):
        return lon, lat
    x, y = lon - 105, lat - 35
    dlat = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    dlon = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    common = (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    dlat += common + (20 * math.sin(y * math.pi) + 40 * math.sin(y / 3 * math.pi)) * 2 / 3
    dlat += (160 * math.sin(y / 12 * math.pi) + 320 * math.sin(y * math.pi / 30)) * 2 / 3
    dlon += common + (20 * math.sin(x * math.pi) + 40 * math.sin(x / 3 * math.pi)) * 2 / 3
    dlon += (150 * math.sin(x / 12 * math.pi) + 300 * math.sin(x / 30 * math.pi)) * 2 / 3
    rad = math.radians(lat)
    magic = 1 - 0.00669342162296594323 * math.sin(rad) ** 2
    dlat = (
        dlat
        * 180
        / ((6378245 * (1 - 0.00669342162296594323)) / (magic * math.sqrt(magic)) * math.pi)
    )
    dlon = dlon * 180 / (6378245 / math.sqrt(magic) * math.cos(rad) * math.pi)
    return lon - dlon, lat - dlat


def resolve_city(city: str, key: str) -> tuple[float, float] | None:
    """Accept one exact administrative city match, never a fuzzy village match."""
    if not key:
        return None
    # urllib avoids HTTP-client INFO logs exposing the AMap query-string key.
    query = urlencode({"key": key, "keywords": city, "subdistrict": 0, "extensions": "base"})
    with urlopen(f"https://restapi.amap.com/v3/config/district?{query}", timeout=8) as response:
        payload = json.load(response)
    if str(payload.get("status")) != "1":
        return None
    normalized = city.strip().removesuffix("市")
    matches = [
        item
        for item in payload.get("districts", [])
        if item.get("level") in {"city", "province"}
        and item.get("name", "").removesuffix("市") == normalized
        and (
            item.get("level") == "city"
            or item.get("name") in {"北京市", "上海市", "天津市", "重庆市"}
        )
    ]
    if len(matches) != 1:
        return None
    lon, lat = map(float, matches[0]["center"].split(","))
    if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return gcj02_to_wgs84(lon, lat)


class WeatherProvider:
    def __init__(self, python: str, amap_key: str):
        self.python = python
        self.amap_key = amap_key

    def collect(self, city: str, start: date, end: date) -> tuple[list[dict], str]:
        try:
            coordinates = resolve_city(city, self.amap_key)
            if coordinates is None:
                return [], "location_unverified"
            lon, lat = coordinates
            bridge = Path(__file__).resolve().parents[2] / "scripts/weather_mcp_bridge.py"
            # Do not forward application secrets to the third-party subprocess.
            env = {
                key: value
                for key, value in os.environ.items()
                if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "LANG"}
            }
            result = subprocess.run(
                [self.python, str(bridge)],
                input=json.dumps({"location": f"{lat},{lon}", "days": 16}),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                env=env,
                check=True,
            )
            payload = json.loads(result.stdout)
            fetched = datetime.now(timezone.utc)
            rows = []
            for item in payload["forecast"]:
                day = date.fromisoformat(item["date"])
                if not start <= day <= end:
                    continue
                # Missing measurements remain unavailable, never become zero degrees.
                if item.get("temp_max_c") is None or item.get("temp_min_c") is None:
                    continue
                row = WeatherInfoV2(
                    city=city,
                    date=day,
                    day_weather=item.get("condition", ""),
                    day_temp=round(item["temp_max_c"]),
                    night_temp=round(item["temp_min_c"]),
                    wind_power=f"{item['wind_max_kmh']} km/h"
                    if item.get("wind_max_kmh") is not None
                    else "",
                    precipitation_probability=item.get("precipitation_prob_pct"),
                    source_url="https://open-meteo.com/",
                    fetched_at=fetched,
                )
                rows.append(row.model_dump(mode="json"))
            by_date = {row["date"]: row for row in rows}
            rows = [by_date[key] for key in sorted(by_date)]
            return rows, "complete" if len(rows) == (
                end - start
            ).days + 1 else "partial_or_out_of_range"
        except Exception:
            # Provider failures must not abort a trip or leak URLs containing keys.
            return [], "weather_unavailable"


def collect_weather(request, settings) -> tuple[dict, dict]:
    weather: dict[str, list[dict]] = {}
    issues = {}
    if not settings.weather_enabled or settings.demo_mode:
        return weather, issues
    provider = WeatherProvider(settings.weather_mcp_python, settings.vite_amap_web_key)
    start = request.start_date
    for destination in request.destinations:
        end = start + timedelta(days=destination.days - 1)
        rows, status = provider.collect(destination.city, start, end)
        weather.setdefault(destination.city, []).extend(rows)
        issues[destination.city] = status
        start = end + timedelta(days=1)
    return weather, issues
