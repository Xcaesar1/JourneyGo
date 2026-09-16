"""Compiled graph for impact-scoped, human-approved dynamic replanning."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ...services.research import NoopWebResearchProvider, WebResearchProvider
from ...services.routing import NoopRouteEstimateProvider, RouteEstimateProvider
from ..journey_graph.nodes.revise import revise_plan
from .nodes import (
    analyze_change_request,
    apply_changes,
    compute_diff,
    enrich_replan,
    finalize_replan,
    make_human_review_node,
    make_refresh_impacted_data_node,
    reject_replan,
    validate_replan,
)
from .state import ReplanState


def build_replan_graph(
    *,
    research_provider: WebResearchProvider | None = None,
    route_provider: RouteEstimateProvider | None = None,
    checkpointer: Any | None = None,
    require_human_review: bool = True,
):
    """Build a durable graph that loops on explicit modify decisions."""
    research = research_provider or NoopWebResearchProvider()
    routing = route_provider or NoopRouteEstimateProvider()
    builder = StateGraph(ReplanState)
    builder.add_node("analyze_change_request", analyze_change_request)
    builder.add_node(
        "refresh_impacted_data",
        make_refresh_impacted_data_node(research, routing),
    )
    builder.add_node("apply_changes", apply_changes)
    builder.add_node("enrich_replan", enrich_replan)
    builder.add_node("validate_replan", validate_replan)
    builder.add_node("revise_replan", revise_plan)
    builder.add_node("compute_diff", compute_diff)
    builder.add_node("human_review", make_human_review_node(require_human_review))
    builder.add_node("finalize_replan", finalize_replan)
    builder.add_node("reject_replan", reject_replan)

    builder.add_edge(START, "analyze_change_request")
    builder.add_edge("analyze_change_request", "refresh_impacted_data")
    builder.add_edge("refresh_impacted_data", "apply_changes")
    builder.add_edge("apply_changes", "enrich_replan")
    builder.add_edge("enrich_replan", "validate_replan")
    builder.add_conditional_edges(
        "validate_replan",
        _after_validation,
        {"revise_replan": "revise_replan", "compute_diff": "compute_diff"},
    )
    builder.add_edge("revise_replan", "enrich_replan")
    builder.add_edge("compute_diff", "human_review")
    builder.add_conditional_edges(
        "human_review",
        _after_review,
        {
            "analyze_change_request": "analyze_change_request",
            "finalize_replan": "finalize_replan",
            "reject_replan": "reject_replan",
        },
    )
    builder.add_edge("finalize_replan", END)
    builder.add_edge("reject_replan", END)
    return builder.compile(checkpointer=checkpointer)


def _after_validation(state: ReplanState) -> str:
    report = state["validation_report"]
    if report.has_critical and state.get("revision_count", 0) < 2:
        return "revise_replan"
    return "compute_diff"


def _after_review(state: ReplanState) -> str:
    action = state.get("review_action")
    if action == "modify":
        return "analyze_change_request"
    if action == "approve":
        return "finalize_replan"
    return "reject_replan"
