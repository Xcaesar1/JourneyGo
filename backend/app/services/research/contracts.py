"""Protocols used to isolate JourneyGraph from concrete search APIs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ...domain.research_models import (
    CommunityResearchResult,
    ResearchQuery,
    ResearchReport,
    SourceEvidence,
    WebSearchResult,
)


@runtime_checkable
class CommunityResearchProvider(Protocol):
    """Optional source for subjective community experience only."""

    name: str

    async def research(
        self,
        city: str,
        keywords: str,
        language: str,
    ) -> CommunityResearchResult: ...


@runtime_checkable
class ResearchCache(Protocol):
    """TTL cache for already classified evidence."""

    async def get(self, provider: str, query: ResearchQuery) -> list[SourceEvidence] | None: ...

    async def set(
        self,
        provider: str,
        query: ResearchQuery,
        evidence: Sequence[SourceEvidence],
        ttl_seconds: int,
    ) -> None: ...


@runtime_checkable
class WebResearchProvider(Protocol):
    """Read-only provider for source-backed, time-sensitive travel research."""

    name: str

    async def search(self, query: ResearchQuery) -> list[WebSearchResult]: ...

    async def research(self, queries: Sequence[ResearchQuery]) -> ResearchReport: ...
