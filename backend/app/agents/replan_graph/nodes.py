"""Nodes for impact-scoped dynamic replanning."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from langgraph.types import interrupt

from ...domain.research_models import ResearchReport
from ...domain.review_models import ReplanRequestV2, TripReviewDecisionV2
from ...domain.trip_models import TripPlanV2, TripRequestV2
from ...services.replanning import analyze_impact, apply_scoped_changes, diff_plans
from ...services.research import WebResearchProvider, prepare_research_queries
from ...services.routing import RouteEstimateProvider
from ..journey_graph.nodes.enrich import enrich_plan
from ..journey_graph.nodes.transport import make_plan_intercity_transport_node
from ..journey_graph.nodes.validate import validate_plan
from ..journey_graph.state import TripState
from .state import ReplanState


def analyze_change_request(state: ReplanState) -> dict[str, Any]:
    change_request = ReplanRequestV2.model_validate(state["change_request"])
    request = TripRequestV2.model_validate(state["request"])
    base_plan = TripPlanV2.model_validate(state["base_plan"])
    original_plan = TripPlanV2.model_validate(state["original_plan"])
    scope = analyze_impact(change_request, base_plan)
    return {
        "change_request": change_request,
        "request": request,
        "base_plan": base_plan,
        "original_plan": original_plan,
        "impact_scope": scope,
        "metrics": {
            **state.get("metrics", {}),
            "impact_analyzed": True,
            "impacted_day_count": len(scope.day_indices),
        },
    }


def make_refresh_impacted_data_node(
    research_provider: WebResearchProvider,
    route_provider: RouteEstimateProvider,
) -> Callable[[ReplanState], dict[str, Any]]:
    route_node = make_plan_intercity_transport_node(route_provider)

    def refresh_impacted_data(state: ReplanState) -> dict[str, Any]:
        scope = state["impact_scope"]
        request = state["request"]
        updates: dict[str, Any] = {
            "sources": [],
            "refreshed_sources": [],
            "metrics": {
                **state.get("metrics", {}),
                "research_refreshed": False,
                "routing_refreshed": False,
            },
        }
        if scope.refresh_research:
            affected_cities = {
                state["base_plan"].days[index].city
                for index in scope.day_indices
                if index < len(state["base_plan"].days)
            }
            queries = [
                query
                for query in prepare_research_queries(request)
                if query.city in affected_cities
            ]
            report = ResearchReport.model_validate(
                asyncio.run(research_provider.research(queries))
            )
            updates["sources"] = report.evidence
            updates["refreshed_sources"] = [str(item.id) for item in report.evidence]
            updates["metrics"] = {
                **updates["metrics"],
                "research_refreshed": True,
                "research_query_count": len(queries),
            }
        if scope.refresh_routing:
            routing_request = request.model_copy(
                update={
                    "transport_preferences": state["change_request"].transport_preferences
                    or request.transport_preferences
                }
            )
            route_update = route_node(
                {"request": routing_request, "metrics": updates["metrics"]}
            )
            updates.update(
                {
                    "route_estimates": route_update["route_estimates"],
                    "transport_options": route_update["transport_options"],
                    "metrics": {
                        **route_update["metrics"],
                        "routing_refreshed": True,
                    },
                }
            )
        return updates

    return refresh_impacted_data


def apply_changes(state: ReplanState) -> dict[str, Any]:
    updated_request, plan, unresolved = apply_scoped_changes(
        trip_request=state["request"],
        base_plan=state["base_plan"],
        change_request=state["change_request"],
        impact_scope=state["impact_scope"],
        route_estimates=(state.get("route_estimates") if state["impact_scope"].refresh_routing else None),
        transport_options=(
            state.get("transport_options") if state["impact_scope"].refresh_routing else None
        ),
        source_evidence=state.get("sources") if state["impact_scope"].refresh_research else None,
    )
    return {
        "request": updated_request,
        "draft_plan": plan,
        "revision_count": 0,
        "unresolved_additions": unresolved,
        "metrics": {
            **state.get("metrics", {}),
            "scoped_changes_applied": True,
            "unresolved_addition_count": len(unresolved),
        },
    }


def enrich_replan(state: ReplanState) -> dict[str, Any]:
    base_plan = TripPlanV2.model_validate(state["base_plan"])
    transport_options = state.get("transport_options") or list(
        base_plan.transport_options
    )
    route_estimates = state.get("route_estimates")
    if route_estimates is None:
        intercity_route_ids = {
            option.route_estimate_id
            for option in transport_options
            if option.route_estimate_id is not None
        }
        route_estimates = [
            route
            for route in base_plan.route_matrix
            if route.estimate_id in intercity_route_ids
        ]
    enrich_state: TripState = {
        "trip_id": state["trip_id"],
        "task_id": state["task_id"],
        "request": state["request"],
        "draft_plan": state["draft_plan"],
        "transport_options": transport_options,
        "route_estimates": route_estimates,
        "metrics": state.get("metrics", {}),
    }
    enriched = enrich_plan(enrich_state)
    enriched_plan = TripPlanV2.model_validate(enriched["draft_plan"])
    impacted = set(state["impact_scope"].day_indices)
    base_days = {day.day_index: day for day in base_plan.days}
    preserved_days = [
        day if day.day_index in impacted else base_days[day.day_index]
        for day in enriched_plan.days
    ]
    enriched["draft_plan"] = enriched_plan.model_copy(
        update={"days": preserved_days}
    )
    return enriched


def validate_replan(state: ReplanState) -> dict[str, Any]:
    return validate_plan(state)  # type: ignore[arg-type]


def compute_diff(state: ReplanState) -> dict[str, Any]:
    diff = diff_plans(
        state["original_plan"],
        state["draft_plan"],
        from_version=state["from_version"],
        to_version=state["proposed_version"],
    )
    return {
        "diff": diff,
        "metrics": {
            **state.get("metrics", {}),
            "diff_computed": True,
            "changed_day_count": len(diff.changed_day_indices),
        },
    }


def make_human_review_node(require_human_review: bool):
    def human_review(state: ReplanState) -> dict[str, Any]:
        if require_human_review:
            raw = interrupt(
                {
                    "kind": "replan_review",
                    "task_id": state["task_id"],
                    "trip_id": state["trip_id"],
                    "from_version": state["from_version"],
                    "proposed_version": state["proposed_version"],
                    "impact_scope": state["impact_scope"].model_dump(mode="json"),
                    "diff": state["diff"].model_dump(mode="json"),
                    "validation_report": state["validation_report"].model_dump(mode="json"),
                }
            )
            decision = TripReviewDecisionV2.model_validate(raw)
        else:
            decision = TripReviewDecisionV2(action="approve")
        update: dict[str, Any] = {
            "review_action": decision.action,
            "review_reason": decision.reason,
            "metrics": {
                **state.get("metrics", {}),
                "human_reviewed": True,
                "human_review_action": decision.action,
            },
        }
        if decision.action == "modify" and decision.changes is not None:
            update.update(
                {
                    "base_plan": state["draft_plan"],
                    "change_request": decision.changes,
                    "replan_round": state.get("replan_round", 0) + 1,
                    "sources": [],
                    "refreshed_sources": [],
                }
            )
        return update

    return human_review


def finalize_replan(state: ReplanState) -> dict[str, Any]:
    return {
        "final_plan": state["draft_plan"],
        "metrics": {**state.get("metrics", {}), "replan_finalized": True},
    }


def reject_replan(state: ReplanState) -> dict[str, Any]:
    return {
        "metrics": {**state.get("metrics", {}), "replan_rejected": True},
    }
