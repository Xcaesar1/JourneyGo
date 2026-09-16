"""Build configured research providers without exposing credentials."""

from __future__ import annotations

import os

from ...config import get_settings
from .cache import NoopResearchCache, RedisResearchCache
from .providers import build_web_research_provider, official_domains_from_string


def build_configured_web_research_provider():
    settings = get_settings()
    redis_url = os.getenv("REDIS_URL", "").strip()
    cache = RedisResearchCache.from_url(redis_url) if redis_url else NoopResearchCache()
    return build_web_research_provider(
        api_key=settings.brave_search_api_key,
        endpoint=settings.brave_search_base_url,
        timeout_seconds=settings.web_research_timeout,
        result_count=settings.web_research_result_count,
        cache=cache,
        cache_ttl_seconds=settings.source_cache_ttl_seconds,
        official_domains=official_domains_from_string(settings.web_research_official_domains),
    )
