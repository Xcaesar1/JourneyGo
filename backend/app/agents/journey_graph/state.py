"""Serializable state contract for the JourneyGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from ...domain.research_models import (
    ProviderCallMetric,
    ProviderIssue,
    ResearchQuery,
    SourceEvidence,
)
from ...domain.trip_models import (
    IntercityTransportOptionV2,
    RouteEstimateV2,
    TripPlanV2,
    TripRequestV2,
)
from ...domain.validation_models import ValidationReportV2


class TripState(TypedDict, total=False):
    trip_id: str
    task_id: str
    request: TripRequestV2
    traveler_profile: dict[str, Any]
    research_queries: list[ResearchQuery]
    sources: list[SourceEvidence]
    research_issues: list[ProviderIssue]
    provider_metrics: list[ProviderCallMetric]
    poi_candidates: dict[str, list[dict[str, Any]]]
    weather: dict[str, list[dict[str, Any]]]
    transport_options: list[IntercityTransportOptionV2]
    route_estimates: list[RouteEstimateV2]
    draft_plan: TripPlanV2
    validation_report: ValidationReportV2
    revision_count: int
    approval_status: str
    review_reason: str
    final_plan: TripPlanV2
    errors: list[dict[str, Any]]
    metrics: dict[str, Any]
