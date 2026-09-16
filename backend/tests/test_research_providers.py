"""Provider failure, ranking, fallback, and cache tests for Phase 4 research."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from backend.app.domain.research_models import (
    ResearchQuery,
    SourceEvidence,
    WebSearchResult,
)
from backend.app.services.research import (
    BraveSearchProvider,
    FallbackWebResearchProvider,
    MemoryResearchCache,
    NoopWebResearchProvider,
    build_web_research_provider,
)
from backend.app.services.research.errors import (
    ProviderAuthenticationError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from backend.app.services.research.ranking import rank_search_results


def _query(*, critical: bool = True) -> ResearchQuery:
    return ResearchQuery(
        id="af931aaa-279f-51b7-8a35-4f8ee621b3f7",
        city="Tokyo",
        claim_type="closure",
        query="Tokyo 2026-10 temporary closure official",
        priority=100,
        critical=critical,
    )


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [(401, ProviderAuthenticationError), (429, ProviderRateLimitError)],
)
async def test_brave_search_classifies_http_failures(status_code: int, error_type: type) -> None:
    client = _client(lambda _request: httpx.Response(status_code, json={"secret": "not-safe"}))
    provider = BraveSearchProvider("test-secret", client=client)

    with pytest.raises(error_type) as exc_info:
        await provider.search(_query())

    assert "test-secret" not in str(exc_info.value)
    assert "not-safe" not in str(exc_info.value)
    await client.aclose()


async def test_brave_search_classifies_timeout() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("contains test-secret", request=request)

    client = _client(timeout_handler)
    provider = BraveSearchProvider("test-secret", client=client)

    with pytest.raises(ProviderTimeoutError) as exc_info:
        await provider.search(_query())

    assert "test-secret" not in str(exc_info.value)
    await client.aclose()


async def test_brave_search_accepts_empty_results() -> None:
    client = _client(lambda _request: httpx.Response(200, json={"web": {"results": []}}))
    provider = BraveSearchProvider("test-secret", client=client)

    assert await provider.search(_query()) == []
    await client.aclose()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"web": {"unexpected": []}}),
        httpx.Response(200, json={"web": {"results": [{"title": "Missing URL"}]}}),
    ],
)
async def test_brave_search_rejects_malformed_json(response: httpx.Response) -> None:
    client = _client(lambda _request: response)
    provider = BraveSearchProvider("test-secret", client=client)

    with pytest.raises(ProviderInvalidResponseError):
        await provider.search(_query())

    await client.aclose()


def test_official_sources_sort_before_community_results() -> None:
    results = [
        WebSearchResult(title="Community", url="https://www.xiaohongshu.com/item/1"),
        WebSearchResult(title="Official", url="https://museum.example/notice"),
        WebSearchResult(title="Government", url="https://alerts.city.gov/closure"),
    ]

    ranked = rank_search_results(results, ("museum.example",))

    assert [item.title for item in ranked] == ["Government", "Official", "Community"]


class FailingProvider:
    name = "failing"

    async def search(self, query: ResearchQuery) -> list[WebSearchResult]:
        _ = query
        raise ProviderRateLimitError()

    async def research(self, queries):
        raise AssertionError("fallback should call search")


class WorkingProvider:
    name = "working"

    async def search(self, query: ResearchQuery) -> list[WebSearchResult]:
        _ = query
        return [
            WebSearchResult(
                title="Official closure notice",
                url="https://tourism.example/closure",
                snippet="The venue remains open during the travel dates.",
            )
        ]

    async def research(self, queries):
        raise AssertionError("fallback should call search")


async def test_fallback_preserves_results_after_one_provider_fails() -> None:
    provider = FallbackWebResearchProvider(
        [FailingProvider(), WorkingProvider()],
        official_domains=("tourism.example",),
    )

    report = await provider.research([_query()])

    assert len(report.evidence) == 1
    assert report.evidence[0].trust_level == "official"
    assert report.issues[0].error_code == "rate_limited"
    assert [metric.success for metric in report.metrics] == [False, True]


async def test_no_key_builds_degraded_unknown_evidence() -> None:
    provider = build_web_research_provider(api_key="")

    report = await provider.research([_query()])

    assert len(report.evidence) == 1
    assert report.evidence[0].freshness_status == "unknown"
    assert report.evidence[0].url is None
    assert report.issues[0].provider == "noop"


async def test_memory_cache_honors_ttl_and_avoids_a_second_provider_call() -> None:
    now = [100.0]
    cache = MemoryResearchCache(clock=lambda: now[0])
    query = _query()
    evidence = SourceEvidence(
        id="9ec52bcb-58f0-50ac-9b61-4f8418ec32a2",
        title="Official source",
        url="https://tourism.example/notice",
        domain="tourism.example",
        provider="working",
        claim_type="closure",
        claim_text="Open.",
        fetched_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
        freshness_status="unknown",
        trust_level="official",
        confidence=0.9,
    )

    await cache.set("working", query, [evidence], ttl_seconds=30)
    assert await cache.get("working", query) == [evidence]

    now[0] = 131.0
    assert await cache.get("working", query) is None


async def test_fallback_uses_cached_evidence() -> None:
    cache = MemoryResearchCache()
    provider = FallbackWebResearchProvider(
        [WorkingProvider()],
        cache=cache,
        official_domains=("tourism.example",),
    )

    first = await provider.research([_query()])
    second = await provider.research([_query()])

    assert first.cache_hits == 0
    assert second.cache_hits == 1
    assert second.metrics[0].cache_hit is True
    assert second.evidence == first.evidence


def test_noop_provider_satisfies_fallback_contract() -> None:
    provider = NoopWebResearchProvider()
    assert provider.name == "noop"
