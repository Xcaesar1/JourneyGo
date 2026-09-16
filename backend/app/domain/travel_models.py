"""Read-only travel search contracts, separate from planning estimates."""

from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TravelSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: Literal["train", "hotel", "flight"]
    destination: str = Field(min_length=1, max_length=100)
    origin: str = Field(default="", max_length=100)
    date: date
    country: str = Field(default="中国", min_length=1, max_length=60)
    nights: int = Field(default=1, ge=1, le=28)
    adults: int = Field(default=2, ge=1, le=4)
    high_speed_only: bool = True
    confirm_paid: bool = False

    @model_validator(mode="after")
    def check_search(self):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        if not today <= self.date <= today + timedelta(days=365):
            raise ValueError("Query date must be within the next 365 days.")
        if self.provider != "hotel" and (not self.origin or self.origin == self.destination):
            raise ValueError("Distinct origin and destination are required.")
        if self.provider == "train" and self.date > today + timedelta(days=14):
            raise ValueError("Train queries support the next 15 calendar days only.")
        if self.provider == "flight":
            for city in (self.origin, self.destination):
                if len(city) != 3 or not city.isascii() or not city.isalpha() or not city.isupper():
                    raise ValueError(
                        "Flight cities require uppercase IATA city codes, e.g. BJS/SHA."
                    )
        return self


class TravelOffer(BaseModel):
    offer_id: str
    title: str
    subtitle: str = ""
    departure: str = ""
    arrival: str = ""
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    currency: str = "CNY"
    price_basis: Literal["per_person", "stay_total"]
    fare_label: str = ""
    availability: str = ""
    booking_url: str = ""
    notes: list[str] = Field(default_factory=list)


class TravelSearchResponse(BaseModel):
    provider: Literal["train", "hotel", "flight"]
    status: Literal["ok", "empty", "disabled", "unavailable", "busy", "budget_exhausted"]
    message: str
    offers: list[TravelOffer] = Field(default_factory=list)
    source_title: str
    source_url: str
    source_domain: str
    trust_level: Literal["major_platform", "unknown"] = "major_platform"
    fetched_at: datetime | None = None
    cached: bool = False
    query: TravelSearchRequest
