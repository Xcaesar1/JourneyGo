"""AMap per-person reference prices; missing prices are not free meals."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .hotel_pricing import amount


class MealPriceReference(BaseModel):
    amount_cents: int = Field(gt=0)
    source: Literal["amap"] = "amap"
    source_url: str = "https://www.amap.com/"
    fetched_at: datetime


def meal_reference(poi: dict) -> MealPriceReference | None:
    business = poi.get("business")
    price = amount(business.get("cost")) if isinstance(business, dict) else None
    if price is None or price <= 0 or not poi.get("fetched_at"):
        return None
    from decimal import ROUND_HALF_UP

    cents = int((price * 100).quantize(1, rounding=ROUND_HALF_UP))
    if cents <= 0:
        return None
    return MealPriceReference(amount_cents=cents, fetched_at=poi["fetched_at"])
