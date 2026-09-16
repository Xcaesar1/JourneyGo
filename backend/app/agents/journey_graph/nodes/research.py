"""Run source-backed web research while preserving partial graph progress."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from ....domain.research_models import ResearchReport
from ....services.research.contracts import WebResearchProvider
from ..state import TripState


def _run_research(provider: WebResearchProvider, state: TripState) -> ResearchReport:
    return asyncio.run(provider.research(state.get("research_queries", [])))


def make_research_web_node(
    provider: WebResearchProvider,
) -> Callable[[TripState], dict[str, Any]]:
    def research_web(state: TripState) -> dict[str, Any]:
        report = ResearchReport.model_validate(_run_research(provider, state))
        issues = [issue.model_dump(mode="json") for issue in report.issues]
        provider_metrics = [metric.model_dump(mode="json") for metric in report.metrics]
        unknown_count = sum(item.trust_level == "unknown" and item.url is None for item in report.evidence)
        return {
            "sources": report.evidence,
            "research_issues": report.issues,
            "provider_metrics": report.metrics,
            "errors": [*state.get("errors", []), *issues],
            "metrics": {
                **state.get("metrics", {}),
                "researched": True,
                "research_evidence_count": len(report.evidence),
                "research_unknown_count": unknown_count,
                "research_cache_hits": report.cache_hits,
                "research_provider_calls": provider_metrics,
            },
        }

    return research_web
