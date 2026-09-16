"""Typed human-review, replanning, diff, and version contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .validation_models import ValidationReportV2

ReviewActionV2 = Literal["approve", "modify", "reject"]
BoundedChangeText = Annotated[str, Field(min_length=1, max_length=200)]
ReviewStatusV2 = Literal[
    "requested",
    "pending",
    "changes_requested",
    "approved",
    "rejected",
    "superseded",
    "applied",
]


class ReplanRequestV2(BaseModel):
    """Bounded, structured changes accepted by the scoped replan workflow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    instruction: str = Field(..., min_length=1, max_length=2000)
    day_indices: list[int] = Field(default_factory=list, max_length=30)
    transport_preferences: list[BoundedChangeText] | None = Field(default=None, max_length=8)
    budget_total: Decimal | None = Field(default=None, gt=0)
    pace: Literal["relaxed", "balanced", "intensive"] | None = None
    add_attractions: list[BoundedChangeText] = Field(default_factory=list, max_length=20)
    remove_attractions: list[BoundedChangeText] = Field(default_factory=list, max_length=20)
    refresh_sources: bool = False

    @model_validator(mode="after")
    def normalize_scope(self) -> ReplanRequestV2:
        self.day_indices = sorted(set(self.day_indices))
        if any(index < 0 or index > 29 for index in self.day_indices):
            raise ValueError("day_indices must be between 0 and 29")
        if self.transport_preferences is not None:
            self.transport_preferences = [
                value for value in dict.fromkeys(self.transport_preferences) if value
            ]
            if not self.transport_preferences:
                raise ValueError("transport_preferences cannot be empty when provided")
        self.add_attractions = [value for value in dict.fromkeys(self.add_attractions) if value]
        self.remove_attractions = [
            value for value in dict.fromkeys(self.remove_attractions) if value
        ]
        overlap = {value.casefold() for value in self.add_attractions} & {
            value.casefold() for value in self.remove_attractions
        }
        if overlap:
            raise ValueError("the same attraction cannot be added and removed")
        return self


class TripReviewDecisionV2(BaseModel):
    """One explicit user decision for an interrupted workflow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: ReviewActionV2
    reason: str = Field(default="", max_length=2000)
    changes: ReplanRequestV2 | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> TripReviewDecisionV2:
        if self.action == "modify" and self.changes is None:
            raise ValueError("changes are required when action is modify")
        if self.action != "modify" and self.changes is not None:
            raise ValueError("changes are only accepted when action is modify")
        if self.action == "reject" and not self.reason:
            raise ValueError("reason is required when action is reject")
        return self


class ImpactScopeV2(BaseModel):
    """Deterministic description of data and days affected by a replan request."""

    model_config = ConfigDict(extra="forbid")

    day_indices: list[int] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    refresh_research: bool = False
    refresh_routing: bool = False
    rebuild_timeline: bool = False
    recalculate_budget: bool = False


class PlanDiffEntryV2(BaseModel):
    """One machine-readable difference between immutable plan versions or drafts."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., min_length=1, max_length=500)
    operation: Literal["add", "remove", "replace"]
    before: Any | None = None
    after: Any | None = None


class PlanDiffV2(BaseModel):
    """Bounded structured diff with explicit changed and preserved day scopes."""

    model_config = ConfigDict(extra="forbid")

    from_version: int | None = Field(default=None, ge=1)
    to_version: int | None = Field(default=None, ge=1)
    summary: str = Field(default="", max_length=2000)
    changed_day_indices: list[int] = Field(default_factory=list)
    unchanged_day_indices: list[int] = Field(default_factory=list)
    entries: list[PlanDiffEntryV2] = Field(default_factory=list, max_length=500)


class TripReviewRecordV2(BaseModel):
    """Public durable review state returned by task and review endpoints."""

    model_config = ConfigDict(extra="forbid")

    review_id: str
    trip_id: str
    task_id: str
    workflow_type: Literal["initial", "replan", "rollback"]
    status: ReviewStatusV2
    base_version: int | None = None
    proposed_version: int | None = None
    parent_review_id: str | None = None
    reason: str = ""
    change_request: ReplanRequestV2 | None = None
    impact_scope: ImpactScopeV2 | None = None
    refreshed_sources: list[str] = Field(default_factory=list)
    validation_report: ValidationReportV2 = Field(default_factory=ValidationReportV2)
    diff: PlanDiffV2 = Field(default_factory=PlanDiffV2)
    preview: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class TripVersionRecordV2(BaseModel):
    """Public immutable version metadata with optional plan payload."""

    model_config = ConfigDict(extra="forbid")

    trip_id: str
    version: int = Field(..., ge=1)
    active: bool = False
    parent_version: int | None = Field(default=None, ge=1)
    planner_engine: str
    version_role: str
    schema_version: str
    review_id: str | None = None
    change_reason: str = ""
    change_sources: list[str] = Field(default_factory=list)
    validation_report: ValidationReportV2 = Field(default_factory=ValidationReportV2)
    model_id: str = "unknown"
    prompt_version: str = "legacy"
    workflow_version: str = "legacy"
    tool_versions: dict[str, str] = Field(default_factory=dict)
    usage_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    payload: dict[str, Any] | None = None
    native_payload: dict[str, Any] | None = None


class VersionRollbackRequestV2(BaseModel):
    """Reason required when creating a new version from an older immutable version."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(..., min_length=1, max_length=2000)
