"""Contract tests for source-backed travel research."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from backend.app.domain.research_models import (
    ResearchQuery,
    ResearchReport,
    SourceEvidence,
    WebSearchResult,
    stable_research_id,
)
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE, TripRequestV2
from backend.app.services.research import WebResearchProvider, prepare_research_queries
from pydantic import ValidationError


class ContractProvider:
    name = "contract"

    async def search(self, query: ResearchQuery) -> list[WebSearchResult]:
        _ = query
        return []

    async def research(self, queries: list[ResearchQuery]) -> ResearchReport:
        _ = queries
        return ResearchReport()


def test_web_research_provider_is_runtime_checkable() -> None:
    assert isinstance(ContractProvider(), WebResearchProvider)


def test_prepare_research_queries_covers_five_fact_categories_per_city() -> None:
    request = TripRequestV2.model_validate(TRIP_REQUEST_V2_EXAMPLE)

    queries = prepare_research_queries(request)

    assert len(queries) == 10
    assert {query.claim_type for query in queries} == {
        "opening_hours",
        "closure",
        "reservation",
        "events",
        "travel_tips",
    }
    assert all(query.city in {"Tokyo", "Kyoto"} for query in queries)
    assert all("2026-10-10 2026-10-14" in query.query for query in queries)
    assert [query.priority for query in queries] == sorted(
        (query.priority for query in queries), reverse=True
    )


def test_research_query_ids_are_stable_across_retries() -> None:
    request = TripRequestV2.model_validate(TRIP_REQUEST_V2_EXAMPLE)

    first = prepare_research_queries(request)
    second = prepare_research_queries(request)

    assert [query.id for query in first] == [query.id for query in second]


def test_source_evidence_rejects_a_domain_that_does_not_match_url() -> None:
    with pytest.raises(ValidationError, match="domain must match"):
        SourceEvidence(
            id=stable_research_id("mismatch"),
            title="Official notice",
            url="https://example.gov/notice",
            domain="untrusted.example",
            provider="contract",
            claim_type="closure",
            claim_text="Closed for maintenance.",
            fetched_at=datetime.now(timezone.utc),
            freshness_status="fresh",
            trust_level="official",
            confidence=0.9,
        )


def test_unknown_source_is_explicit_and_contains_no_invented_url() -> None:
    query = prepare_research_queries(
        TripRequestV2.model_validate(TRIP_REQUEST_V2_EXAMPLE)
    )[0]

    evidence = SourceEvidence.unknown(
        query,
        fetched_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
    )

    assert evidence.url is None
    assert evidence.domain == ""
    assert evidence.freshness_status == "unknown"
    assert evidence.trust_level == "unknown"
    assert evidence.confidence == 0

