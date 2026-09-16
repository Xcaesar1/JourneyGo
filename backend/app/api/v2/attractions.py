"""Attraction discovery API used before itinerary generation."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Query

from ...domain.attraction_models import AttractionCandidatePage
from ...services.attraction_discovery import build_configured_attraction_discovery_provider

router = APIRouter(prefix="/attractions", tags=["API v2"])


@router.get("/candidates", response_model=AttractionCandidatePage)
async def attraction_candidates(
    city: Annotated[str, Query(min_length=1, max_length=120)],
    days: Annotated[int, Query(ge=1, le=30)] = 1,
    limit: Annotated[int, Query(ge=1, le=40)] = 40,
    interests: Annotated[list[str] | None, Query()] = None,
    must_visit: Annotated[list[str] | None, Query()] = None,
    avoid: Annotated[list[str] | None, Query()] = None,
) -> AttractionCandidatePage:
    provider = build_configured_attraction_discovery_provider()
    return await asyncio.to_thread(
        provider.discover,
        city,
        interests=interests or (),
        must_visit=must_visit or (),
        avoid=avoid or (),
        days=days,
        limit=limit,
    )
