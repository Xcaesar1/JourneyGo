"""Online, no-op, and fallback web research providers."""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from ...domain.research_models import (
    ProviderCallMetric,
    ProviderIssue,
    ResearchQuery,
    ResearchReport,
    SourceEvidence,
    WebSearchResult,
    stable_research_id,
)
from .cache import NoopResearchCache
from .contracts import ResearchCache, WebResearchProvider
from .errors import (
    ProviderAuthenticationError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ResearchProviderError,
)
from .ranking import (
    classify_trust,
    confidence_for_trust,
    freshness_for_result,
    normalized_domain,
    rank_search_results,
)

BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchProvider:
    """Brave Search REST adapter using its documented subscription-token header."""

    name = "brave"

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = BRAVE_SEARCH_ENDPOINT,
        timeout_seconds: float = 10,
        result_count: int = 5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Brave Search API key is required.")
        self._api_key = api_key.strip()
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._result_count = result_count
        self._client = client

    async def search(self, query: ResearchQuery) -> list[WebSearchResult]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            try:
                response = await client.get(
                    self._endpoint,
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": self._api_key,
                    },
                    params={"q": query.query, "count": self._result_count},
                    timeout=self._timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError() from exc
            except httpx.RequestError as exc:
                raise ProviderUnavailableError() from exc

            if response.status_code in {401, 403}:
                raise ProviderAuthenticationError()
            if response.status_code == 429:
                raise ProviderRateLimitError()
            if not 200 <= response.status_code < 300:
                raise ProviderUnavailableError()

            try:
                payload = response.json()
                raw_results = payload["web"]["results"]
            except (ValueError, TypeError, KeyError) as exc:
                raise ProviderInvalidResponseError() from exc
            if not isinstance(raw_results, list):
                raise ProviderInvalidResponseError()

            results: list[WebSearchResult] = []
            for item in raw_results:
                if not isinstance(item, dict):
                    raise ProviderInvalidResponseError()
                try:
                    results.append(
                        WebSearchResult(
                            title=item.get("title"),
                            url=item.get("url"),
                            snippet=item.get("description") or "",
                        )
                    )
                except ValidationError as exc:
                    raise ProviderInvalidResponseError() from exc
            return results
        finally:
            if owns_client:
                await client.aclose()

    async def research(self, queries: Sequence[ResearchQuery]) -> ResearchReport:
        return await FallbackWebResearchProvider([self]).research(queries)


class NoopWebResearchProvider:
    """Safe provider used when no online search key is configured."""

    name = "noop"

    async def search(self, query: ResearchQuery) -> list[WebSearchResult]:
        _ = query
        return []

    async def research(self, queries: Sequence[ResearchQuery]) -> ResearchReport:
        report = ResearchReport()
        for query in queries:
            report.issues.append(
                ProviderIssue(
                    provider=self.name,
                    query_id=query.id,
                    error_code="unavailable",
                    message="Online research is not configured.",
                )
            )
            report.metrics.append(
                ProviderCallMetric(
                    provider=self.name,
                    query_id=query.id,
                    latency_ms=0,
                    success=False,
                    error_code="unavailable",
                )
            )
            if query.critical:
                report.evidence.append(SourceEvidence.unknown(query))
        return report


class FallbackWebResearchProvider:
    """Try providers independently and preserve partial results when one fails."""

    name = "fallback"

    def __init__(
        self,
        providers: Sequence[WebResearchProvider],
        *,
        cache: ResearchCache | None = None,
        cache_ttl_seconds: int = 21600,
        official_domains: Sequence[str] = (),
        max_evidence_per_query: int = 3,
    ) -> None:
        self._providers = list(providers) or [NoopWebResearchProvider()]
        self._cache = cache or NoopResearchCache()
        self._cache_ttl_seconds = cache_ttl_seconds
        self._official_domains = tuple(official_domains)
        self._max_evidence_per_query = max_evidence_per_query

    async def search(self, query: ResearchQuery) -> list[WebSearchResult]:
        for provider in self._providers:
            try:
                results = await provider.search(query)
            except Exception:
                continue
            if results:
                return rank_search_results(results, self._official_domains)
        return []

    async def research(self, queries: Sequence[ResearchQuery]) -> ResearchReport:
        report = ResearchReport()
        for query in queries:
            resolved = False
            for provider in self._providers:
                cached = await self._cache_get(provider.name, query)
                if cached is not None:
                    report.cache_hits += 1
                    report.metrics.append(
                        ProviderCallMetric(
                            provider=provider.name,
                            query_id=query.id,
                            latency_ms=0,
                            success=bool(cached),
                            error_code=None if cached else "empty_results",
                            cache_hit=True,
                        )
                    )
                    if cached:
                        report.evidence.extend(cached)
                        resolved = True
                        break
                    report.issues.append(self._empty_issue(provider.name, query))
                    continue

                started_at = time.monotonic()
                try:
                    results = await provider.search(query)
                    elapsed = self._elapsed_ms(started_at)
                    if not results:
                        await self._cache_set(provider.name, query, [])
                        report.issues.append(self._empty_issue(provider.name, query))
                        report.metrics.append(
                            ProviderCallMetric(
                                provider=provider.name,
                                query_id=query.id,
                                latency_ms=elapsed,
                                success=False,
                                error_code="empty_results",
                            )
                        )
                        continue

                    evidence = self._make_evidence(query, provider.name, results)
                    await self._cache_set(provider.name, query, evidence)
                    report.evidence.extend(evidence)
                    report.metrics.append(
                        ProviderCallMetric(
                            provider=provider.name,
                            query_id=query.id,
                            latency_ms=elapsed,
                            success=True,
                        )
                    )
                    resolved = True
                    break
                except ResearchProviderError as exc:
                    report.issues.append(
                        ProviderIssue(
                            provider=provider.name,
                            query_id=query.id,
                            error_code=exc.error_code,
                            message=exc.safe_message,
                        )
                    )
                    report.metrics.append(
                        ProviderCallMetric(
                            provider=provider.name,
                            query_id=query.id,
                            latency_ms=self._elapsed_ms(started_at),
                            success=False,
                            error_code=exc.error_code,
                        )
                    )
                except Exception:
                    report.issues.append(
                        ProviderIssue(
                            provider=provider.name,
                            query_id=query.id,
                            error_code="unavailable",
                            message="Research provider is unavailable.",
                        )
                    )
                    report.metrics.append(
                        ProviderCallMetric(
                            provider=provider.name,
                            query_id=query.id,
                            latency_ms=self._elapsed_ms(started_at),
                            success=False,
                            error_code="unavailable",
                        )
                    )

            if not resolved and query.critical:
                report.evidence.append(SourceEvidence.unknown(query))
        return report

    async def _cache_get(
        self,
        provider: str,
        query: ResearchQuery,
    ) -> list[SourceEvidence] | None:
        try:
            return await self._cache.get(provider, query)
        except Exception:
            return None

    async def _cache_set(
        self,
        provider: str,
        query: ResearchQuery,
        evidence: Sequence[SourceEvidence],
    ) -> None:
        try:
            await self._cache.set(
                provider,
                query,
                evidence,
                self._cache_ttl_seconds,
            )
        except Exception:
            return

    def _make_evidence(
        self,
        query: ResearchQuery,
        provider: str,
        results: list[WebSearchResult],
    ) -> list[SourceEvidence]:
        fetched_at = datetime.now(timezone.utc)
        ranked = rank_search_results(results, self._official_domains)
        evidence: list[SourceEvidence] = []
        seen_urls: set[str] = set()
        for result in ranked:
            normalized_url = str(result.url)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            trust_level = classify_trust(normalized_url, self._official_domains)
            evidence.append(
                SourceEvidence(
                    id=stable_research_id(
                        str(query.id),
                        provider,
                        normalized_url,
                        fetched_at.strftime("%Y-%m-%dT%H"),
                    ),
                    title=result.title,
                    url=result.url,
                    domain=normalized_domain(normalized_url),
                    provider=provider,
                    claim_type=query.claim_type,
                    claim_text=result.snippet or result.title,
                    published_at=result.published_at,
                    fetched_at=fetched_at,
                    freshness_status=freshness_for_result(result, observed_at=fetched_at),
                    trust_level=trust_level,
                    confidence=confidence_for_trust(trust_level),
                )
            )
            if len(evidence) >= self._max_evidence_per_query:
                break
        return evidence

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(0, round((time.monotonic() - started_at) * 1000))

    @staticmethod
    def _empty_issue(provider: str, query: ResearchQuery) -> ProviderIssue:
        return ProviderIssue(
            provider=provider,
            query_id=query.id,
            error_code="empty_results",
            message="Research provider returned no results.",
        )


def official_domains_from_string(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def build_web_research_provider(
    *,
    api_key: str,
    endpoint: str = BRAVE_SEARCH_ENDPOINT,
    timeout_seconds: float = 10,
    result_count: int = 5,
    cache: ResearchCache | None = None,
    cache_ttl_seconds: int = 21600,
    official_domains: Sequence[str] = (),
    client: httpx.AsyncClient | None = None,
) -> FallbackWebResearchProvider:
    providers: list[WebResearchProvider]
    if api_key.strip():
        providers = [
            BraveSearchProvider(
                api_key,
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
                result_count=result_count,
                client=client,
            )
        ]
    else:
        providers = [NoopWebResearchProvider()]
    return FallbackWebResearchProvider(
        providers,
        cache=cache,
        cache_ttl_seconds=cache_ttl_seconds,
        official_domains=official_domains,
    )
