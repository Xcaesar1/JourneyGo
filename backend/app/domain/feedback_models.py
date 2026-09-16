"""Bounded API contracts for persistent trip feedback."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FeedbackCategoryV2 = Literal["plan_quality", "sources", "transport", "usability", "other"]


class TripFeedbackRequestV2(BaseModel):
    """User feedback that can be stored without invoking a model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rating: int | None = Field(default=None, ge=1, le=5)
    category: FeedbackCategoryV2 = "other"
    comment: str = Field(default="", max_length=2000)
    version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_feedback_content(self) -> TripFeedbackRequestV2:
        if self.rating is None and not self.comment:
            raise ValueError("rating or comment is required")
        return self


class TripFeedbackRecordV2(BaseModel):
    """Public representation of one immutable feedback submission."""

    model_config = ConfigDict(from_attributes=True)

    feedback_id: str
    trip_id: str
    task_id: str
    rating: int | None = None
    category: FeedbackCategoryV2
    comment: str = ""
    version: int | None = None
    created_at: datetime
