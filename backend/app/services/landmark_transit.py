"""Transit-first landmark transfers with explicitly unpriced driving fallback."""

from math import ceil

import httpx

DRIVING_NOTE = "公共交通优先，远距离或无可用公共交通时采用高德驾车路线兜底，并预留30分钟接驳时间；可自行驾车或尝试网约车/顺风车，需自行确认接单、接送点及景区车辆通行限制；费用未评估、不计入预算，非已预约车辆"


def query_driving(key, arguments):
    with httpx.Client(timeout=20) as client:
        response = client.get(
            "https://restapi.amap.com/v3/direction/driving",
            params={"key": key, **arguments},
        )
        response.raise_for_status()
        return response.json()


def choose_driving(payload):
    if not isinstance(payload, dict) or str(payload.get("status")) != "1":
        return None
    route = payload.get("route")
    if not isinstance(route, dict) or not isinstance(route.get("paths"), list):
        return None
    choices = []
    for path in route["paths"]:
        try:
            minutes = ceil(float(path["duration"]) / 60)
            distance = ceil(float(path["distance"]))
            if not 0 < minutes < 720 or distance <= 0:
                continue
            choices.append({
                "minutes": minutes + 30,
                "distance_meters": distance,
                "walking_minutes": 0,
                "lines": [],
                "mode": "driving",
                "status": "estimated",
                "note": DRIVING_NOTE,
            })
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return min(choices, key=lambda row: row["minutes"]) if choices else None


def query_transit(key, arguments):
    with httpx.Client(timeout=20) as client:
        response = client.get(
            "https://restapi.amap.com/v3/direction/transit/integrated",
            params={"key": key, **arguments},
        )
        response.raise_for_status()
        return response.json()


def choose_transit(payload, walking_limit=90):
    if not isinstance(payload, dict) or str(payload.get("status")) != "1":
        return None
    choices = []
    for route in payload.get("route", {}).get("transits", []):
        try:
            segments = route.get("segments", [])
            lines = [
                line["name"]
                for segment in segments
                for line in segment.get("bus", {}).get("buslines", [])
                if line.get("name")
            ]
            # AMap emits railway placeholders containing only empty arrays on bus routes.
            def populated(value):
                return any(value.values()) if isinstance(value, dict) else bool(value)

            if not lines or any(
                populated(segment.get("taxi")) or populated(segment.get("railway"))
                for segment in segments
            ):
                continue
            duration = ceil(float(route["duration"]) / 60)
            walking = ceil(float(route["walking_distance"]) / 70)
            if not 0 < duration < 720 or walking > walking_limit:
                continue
            distance = None
            try:
                value = float(route.get("distance"))
                if 0 < value < float("inf"):
                    distance = ceil(value)
            except (TypeError, ValueError, OverflowError):
                pass
            choices.append(
                {
                    "minutes": duration + 15,
                    "distance_meters": distance,
                    "walking_minutes": walking,
                    "lines": list(dict.fromkeys(lines)),
                    "mode": "public_transit",
                    "status": "estimated",
                    "note": "高德公共交通方案（公交、地铁等）与15分钟机动预留，实际班次和营业时间需出发前复核",
                }
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return min(choices, key=lambda row: row["minutes"]) if choices else None
