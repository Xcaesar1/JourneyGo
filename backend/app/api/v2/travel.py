"""On-demand quotes. Never called automatically by the planner or its retries."""

from fastapi import APIRouter, HTTPException, Request

from ...config import get_settings
from ...domain.travel_models import TravelSearchRequest, TravelSearchResponse
from ...services.guardrails import enforce_travel_guardrails
from ...services.travel_search import capabilities, search

router = APIRouter(prefix="/travel", tags=["API v2"])


@router.get("/capabilities")
def travel_capabilities():
    return capabilities(get_settings())


@router.post("/search", response_model=TravelSearchResponse)
def travel_search(payload: TravelSearchRequest, request: Request):
    settings = get_settings()
    enforce_travel_guardrails(request, settings, paid=payload.provider == "flight")
    if payload.provider == "flight" and not payload.confirm_paid:
        raise HTTPException(status_code=422, detail="请先确认本次航班查询可能产生费用。")
    return search(payload, settings)
