"""Prepare bounded, typed research questions without an external call."""

from __future__ import annotations

from typing import Any

from ....services.research.queries import prepare_research_queries as generate_queries
from ..state import TripState


def prepare_research_queries(state: TripState) -> dict[str, Any]:
    queries = generate_queries(state["request"])
    return {
        "research_queries": queries,
        "metrics": {
            **state.get("metrics", {}),
            "research_prepared": True,
            "research_query_count": len(queries),
        },
    }
