"""Read-only real weather + deterministic graph smoke; no LLM or database writes."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.app.adapters.trip_plan import trip_plan_v2_to_legacy
from backend.app.agents.journey_graph import build_journey_graph
from backend.app.config import get_settings
from backend.app.domain.trip_models import TripRequestV2
from backend.app.services.weather import resolve_city


def main():
    settings = get_settings()
    city = "\u897f\u5b89"
    coordinates = resolve_city(city, settings.vite_amap_web_key)
    assert coordinates and 108 < coordinates[0] < 110 and 33 < coordinates[1] < 35
    start = datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
    request = TripRequestV2(
        origin=city,
        destinations=[{"city": city, "days": 2}],
        start_date=start,
        end_date=start + timedelta(days=1),
        travel_days=2,
    )
    result = build_journey_graph(weather_settings=settings).invoke(
        {
            "request": request,
            "trip_id": "weather-smoke",
            "task_id": "weather-smoke",
        }
    )
    plan = trip_plan_v2_to_legacy(result["final_plan"])
    assert len(plan.weather_info) == 2, result.get("metrics", {}).get("weather_status")
    assert all(row.city == city and row.source_url and row.fetched_at for row in plan.weather_info)
    print(
        json.dumps(
            {
                "success": True,
                "coordinates_wgs84": coordinates,
                "data": plan.model_dump(mode="json"),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
