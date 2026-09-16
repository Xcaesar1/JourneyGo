"""Classify and rank web sources with explicit official-domain rules."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from ...domain.research_models import FreshnessStatus, TrustLevel, WebSearchResult

_GOVERNMENT_HOST = re.compile(r"(?:^|\.)gov(?:\.[a-z]{2,3})?$")
_OFFICIAL_SUFFIXES = ("go.jp", "gouv.fr", "gc.ca", "europa.eu")
_COMMUNITY_DOMAINS = (
    "xiaohongshu.com",
    "xhslink.com",
    "rednote.com",
    "tripadvisor.com",
)
_MAJOR_PLATFORM_DOMAINS = (
    "wikipedia.org",
    "wikivoyage.org",
    "lonelyplanet.com",
)
_TRUST_RANK: dict[TrustLevel, int] = {
    "official": 0,
    "major_platform": 1,
    "unknown": 2,
    "community": 3,
}


def normalized_domain(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _matches_domain(host: str, candidate: str) -> bool:
    normalized = candidate.strip().lower().removeprefix("www.").rstrip(".")
    return bool(normalized) and (host == normalized or host.endswith(f".{normalized}"))


def classify_trust(url: str, official_domains: tuple[str, ...] = ()) -> TrustLevel:
    """Only classify a source as official through an allowlist or government suffix."""
    host = normalized_domain(url)
    if any(_matches_domain(host, domain) for domain in official_domains):
        return "official"
    if _GOVERNMENT_HOST.search(host) or any(_matches_domain(host, item) for item in _OFFICIAL_SUFFIXES):
        return "official"
    if any(_matches_domain(host, item) for item in _COMMUNITY_DOMAINS):
        return "community"
    if any(_matches_domain(host, item) for item in _MAJOR_PLATFORM_DOMAINS):
        return "major_platform"
    return "unknown"


def confidence_for_trust(trust_level: TrustLevel) -> float:
    return {
        "official": 0.9,
        "major_platform": 0.7,
        "community": 0.35,
        "unknown": 0.5,
    }[trust_level]


def freshness_for_result(
    result: WebSearchResult,
    *,
    observed_at: datetime,
) -> FreshnessStatus:
    if result.published_at is None:
        return "unknown"
    published_at = result.published_at
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return "fresh" if (observed_at - published_at).days <= 30 else "stale"


def rank_search_results(
    results: list[WebSearchResult],
    official_domains: tuple[str, ...] = (),
) -> list[WebSearchResult]:
    """Put official sources first while preserving deterministic ordering."""
    return sorted(
        results,
        key=lambda item: (
            _TRUST_RANK[classify_trust(str(item.url), official_domains)],
            normalized_domain(str(item.url)),
            item.title.lower(),
        ),
    )
