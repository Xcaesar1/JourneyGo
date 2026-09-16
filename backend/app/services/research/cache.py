"""TTL caches for source evidence."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Callable, Sequence

from redis import Redis

from ...domain.research_models import ResearchQuery, SourceEvidence


def _cache_key(provider: str, query: ResearchQuery) -> str:
    material = f"{provider.strip().lower()}\x1f{query.id}\x1f{query.query}".encode()
    return f"journeyops:research:v1:{hashlib.sha256(material).hexdigest()}"


class NoopResearchCache:
    async def get(self, provider: str, query: ResearchQuery) -> list[SourceEvidence] | None:
        _ = provider, query
        return None

    async def set(
        self,
        provider: str,
        query: ResearchQuery,
        evidence: Sequence[SourceEvidence],
        ttl_seconds: int,
    ) -> None:
        _ = provider, query, evidence, ttl_seconds


class MemoryResearchCache:
    """Small deterministic cache used by unit tests and local execution."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, tuple[float, list[dict]]] = {}

    async def get(self, provider: str, query: ResearchQuery) -> list[SourceEvidence] | None:
        key = _cache_key(provider, query)
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at <= self._clock():
            self._entries.pop(key, None)
            return None
        return [SourceEvidence.model_validate(item) for item in payload]

    async def set(
        self,
        provider: str,
        query: ResearchQuery,
        evidence: Sequence[SourceEvidence],
        ttl_seconds: int,
    ) -> None:
        self._entries[_cache_key(provider, query)] = (
            self._clock() + ttl_seconds,
            [item.model_dump(mode="json") for item in evidence],
        )


class RedisResearchCache:
    """Shared cache used by API and worker processes in staging and production."""

    def __init__(self, client: Redis, *, namespace: str = "journeyops:research:v1") -> None:
        self._client = client
        self._namespace = namespace.rstrip(":")

    @classmethod
    def from_url(cls, redis_url: str) -> RedisResearchCache:
        return cls(Redis.from_url(redis_url, decode_responses=True))

    def _key(self, provider: str, query: ResearchQuery) -> str:
        digest = _cache_key(provider, query).rsplit(":", 1)[-1]
        return f"{self._namespace}:{digest}"

    async def get(self, provider: str, query: ResearchQuery) -> list[SourceEvidence] | None:
        payload = await asyncio.to_thread(self._client.get, self._key(provider, query))
        if payload is None:
            return None
        try:
            decoded = json.loads(payload)
            if not isinstance(decoded, list):
                return None
            return [SourceEvidence.model_validate(item) for item in decoded]
        except (ValueError, TypeError):
            return None

    async def set(
        self,
        provider: str,
        query: ResearchQuery,
        evidence: Sequence[SourceEvidence],
        ttl_seconds: int,
    ) -> None:
        payload = json.dumps(
            [item.model_dump(mode="json") for item in evidence],
            ensure_ascii=True,
            separators=(",", ":"),
        )
        await asyncio.to_thread(
            self._client.set,
            self._key(provider, query),
            payload,
            ex=ttl_seconds,
        )
