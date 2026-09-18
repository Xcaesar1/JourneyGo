"""Manual read-only quotes and feature capabilities; one-click uses the durable ledger."""

from fastapi import APIRouter, HTTPException, Request

from ...config import get_settings
from ...domain.flight_cities import FLIGHT_CITIES
from ...domain.travel_models import TravelSearchRequest, TravelSearchResponse
from ...services.guardrails import enforce_travel_guardrails
from ...services.travel_search import capabilities, search

router = APIRouter(prefix="/travel", tags=["API v2"])


@router.get("/capabilities")
def travel_capabilities():
    settings = get_settings()
    return {
        **capabilities(settings),
        "flight": {**capabilities(settings)["flight"], "city_codes": FLIGHT_CITIES},
        "personal_map": {"enabled": bool(settings.amap_personal_map_enabled and settings.vite_amap_web_key)},
        "one_click": {
            "enabled": settings.one_click_travel_enabled
            and settings.planner_engine == "journey_graph",
            "paid": False,
        },
    }


@router.post("/search", response_model=TravelSearchResponse)
def travel_search(payload: TravelSearchRequest, request: Request):
    settings = get_settings()
    enforce_travel_guardrails(request, settings, paid=payload.provider == "flight")
    if payload.provider == "flight" and not payload.confirm_paid:
        raise HTTPException(status_code=422, detail="请先确认本次航班查询可能产生费用。")
    return search(payload, settings)
