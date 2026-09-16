"""Serializable state for scoped dynamic replanning."""

from __future__ import annotations

from typing import Any, TypedDict

from ...domain.research_models import SourceEvidence
from ...domain.review_models import ImpactScopeV2, PlanDiffV2, ReplanRequestV2
from ...domain.trip_models import (
    IntercityTransportOptionV2,
    RouteEstimateV2,
    TripPlanV2,
    TripRequestV2,
)
from ...domain.validation_models import ValidationReportV2


class ReplanState(TypedDict, total=False):
    trip_id: str
    task_id: str
    thread_id: str
    request: TripRequestV2
    original_plan: TripPlanV2
    base_plan: TripPlanV2
    draft_plan: TripPlanV2
    final_plan: TripPlanV2
    change_request: ReplanRequestV2
    impact_scope: ImpactScopeV2
    sources: list[SourceEvidence]
    refreshed_sources: list[str]
    route_estimates: list[RouteEstimateV2]
    transport_options: list[IntercityTransportOptionV2]
    validation_report: ValidationReportV2
    revision_count: int
    from_version: int | None
    proposed_version: int
    diff: PlanDiffV2
    review_action: str
    review_reason: str
    replan_round: int
    unresolved_additions: list[str]
    errors: list[dict[str, Any]]
    metrics: dict[str, Any]
