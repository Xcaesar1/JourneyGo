"""Typed attraction discovery and image metadata contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AttractionImage(BaseModel):
    """Remote image metadata without storing or mirroring image bytes."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = ""
    source: str = "placeholder"
    author: str = ""
    license: str = ""
    source_page: str = ""
    attribution: str = ""


class AttractionCandidate(BaseModel):
    """One AMap-verified candidate available to users and the planner."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    poi_id: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=120)
    address: str = Field(default="", max_length=500)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    category: str = Field(default="attraction", max_length=200)
    rating: float | None = Field(default=None, ge=0, le=5)
    image: AttractionImage = Field(default_factory=AttractionImage)
    recommendation_score: float = Field(default=0, ge=0, le=100)
    recommendation_reason: str = Field(default="", max_length=500)
    matched_interests: list[str] = Field(default_factory=list, max_length=12)
    is_must_visit: bool = False


class AttractionCandidatePage(BaseModel):
    """Bounded candidate response used by the pre-generation selector."""

    model_config = ConfigDict(extra="forbid")

    city: str
    items: list[AttractionCandidate]
    total: int = Field(ge=0)
    default_selected_ids: list[str] = Field(default_factory=list)
    degraded: bool = False
    issues: list[str] = Field(default_factory=list)
