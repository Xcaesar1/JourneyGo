"""Human approval boundary for the initial JourneyGraph proposal."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from ....domain.review_models import TripReviewDecisionV2
from ..state import TripState


def make_human_review_node(require_human_review: bool):
    """Pause with a serializable preview, or auto-approve in unit/legacy compatibility mode."""

    def human_review(state: TripState) -> dict[str, Any]:
        if require_human_review:
            raw = interrupt(
                {
                    "kind": "trip_plan_review",
                    "task_id": state["task_id"],
                    "trip_id": state["trip_id"],
                    "validation_report": state["validation_report"].model_dump(mode="json"),
                }
            )
            decision = TripReviewDecisionV2.model_validate(raw)
        else:
            decision = TripReviewDecisionV2(action="approve")
        if decision.action == "modify":
            raise ValueError("Initial modifications must enter the scoped Replan Graph.")
        return {
            "approval_status": "approved" if decision.action == "approve" else "rejected",
            "review_reason": decision.reason,
            "metrics": {
                **state.get("metrics", {}),
                "human_reviewed": True,
                "human_review_action": decision.action,
            },
        }

    return human_review


def reject_plan(state: TripState) -> dict[str, Any]:
    """Terminate without creating an immutable plan version."""
    return {
        "approval_status": "rejected",
        "metrics": {**state.get("metrics", {}), "rejected": True},
    }
