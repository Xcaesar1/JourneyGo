"""Phase 3 persistence boundary; database persistence is wired by the worker later."""

from __future__ import annotations

from typing import Any

from ..state import TripState


def persist(state: TripState) -> dict[str, Any]:
    report = state["validation_report"]
    return {
        "final_plan": state["draft_plan"],
        "metrics": {
            **state.get("metrics", {}),
            "persisted": True,
            "unresolved_critical_count": sum(
                issue.severity == "critical" for issue in report.issues
            ),
        },
    }
