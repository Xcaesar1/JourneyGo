"""JourneyGraph integration tests for Phase 4 research nodes."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.agents.journey_graph import build_journey_graph
from backend.app.domain.research_models import (
    ProviderCallMetric,
    ResearchQuery,
    ResearchReport,
    SourceEvidence,
)
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE


class GraphResearchProvider:
    name = "graph-test"

    async def search(self, query: ResearchQuery):
        _ = query
        return []

    async def research(self, queries):
        query = queries[0]
        return ResearchReport(
            evidence=[
                SourceEvidence(
                    id="b3896f49-e6f8-505f-b748-25a8ac89bca1",
                    title="Official notice",
                    url="https://tourism.example/notice",
                    domain="tourism.example",
                    provider=self.name,
                    claim_type=query.claim_type,
                    claim_text="Official planning notice.",
                    fetched_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
                    freshness_status="unknown",
                    trust_level="official",
                    confidence=0.9,
                )
            ],
            metrics=[
                ProviderCallMetric(
                    provider=self.name,
                    query_id=query.id,
                    latency_ms=5,
                    success=True,
                )
            ],
        )


def test_graph_persists_source_evidence_and_provider_metrics_in_state() -> None:
    result = build_journey_graph(research_provider=GraphResearchProvider()).invoke(
        {
            "trip_id": "trip_research",
            "task_id": "task_research",
            "request": TRIP_REQUEST_V2_EXAMPLE,
        }
    )

    assert result["sources"][0].domain == "tourism.example"
    assert result["provider_metrics"][0].provider == "graph-test"
    assert result["metrics"]["research_evidence_count"] == 1
    assert result["errors"] == []
    assert result["final_plan"].source_evidence == result["sources"]
    assert result["final_plan"].research_status == "complete"
    assert result["final_plan"].research_updated_at == datetime(
        2026, 8, 8, tzinfo=timezone.utc
    )
