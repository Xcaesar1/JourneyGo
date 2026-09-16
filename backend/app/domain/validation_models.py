"""Typed validation results shared by JourneyGraph nodes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ValidationIssueV2(BaseModel):
    """One deterministic issue emitted by a validation rule."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(..., min_length=1, max_length=120)
    severity: Literal["info", "warning", "critical"]
    day_index: int | None = Field(default=None, ge=0, le=29)
    item_id: str | None = Field(default=None, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list)
    suggested_action: str | None = Field(default=None, max_length=2000)


class ValidationReportV2(BaseModel):
    """Deterministic validation summary stored in graph state."""

    model_config = ConfigDict(extra="forbid")

    issues: list[ValidationIssueV2] = Field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(issue.severity == "critical" for issue in self.issues)
