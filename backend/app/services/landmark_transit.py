"""Public transit evidence for dedicated landmark days; never substitute driving."""

from math import ceil

import httpx


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
            choices.append(
                {
                    "minutes": duration + 15,
                    "walking_minutes": walking,
                    "lines": list(dict.fromkeys(lines)),
                    "mode": "public_transit",
                    "status": "estimated",
                    "note": "高德公交方案与15分钟机动预留，实际班次和营业时间需出发前复核",
                }
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return min(choices, key=lambda row: row["minutes"]) if choices else None
