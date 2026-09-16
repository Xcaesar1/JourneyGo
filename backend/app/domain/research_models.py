"""Typed source evidence and research results for time-sensitive travel facts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

RESEARCH_ID_NAMESPACE = UUID("f41b49cf-9409-4b48-a783-bf0d29d883fa")

ClaimType = Literal[
    "opening_hours",
    "closure",
    "reservation",
    "events",
    "travel_tips",
]
FreshnessStatus = Literal["fresh", "stale", "unknown"]
TrustLevel = Literal["official", "major_platform", "community", "unknown"]


def stable_research_id(*parts: str) -> UUID:
    """Create repeatable identifiers so retries do not duplicate research records."""
    normalized = "\x1f".join(part.strip().lower() for part in parts)
    return uuid5(RESEARCH_ID_NAMESPACE, normalized)


class ResearchQuery(BaseModel):
    """One bounded web-research question for a city and fact category."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: UUID
    city: str = Field(..., min_length=1, max_length=120)
    claim_type: ClaimType
    query: str = Field(..., min_length=1, max_length=400)
    priority: int = Field(..., ge=1, le=100)
    critical: bool = False


class WebSearchResult(BaseModel):
    """Provider-neutral result returned before evidence classification."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=500)
    url: HttpUrl
    snippet: str = Field(default="", max_length=4000)
    published_at: datetime | None = None


class SourceEvidence(BaseModel):
    """Traceable evidence for one travel claim, or an explicit unknown marker."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: UUID
    title: str = Field(..., min_length=1, max_length=500)
    url: HttpUrl | None = None
    domain: str = Field(default="", max_length=253)
    provider: str = Field(..., min_length=1, max_length=120)
    claim_type: ClaimType
    claim_text: str = Field(..., min_length=1, max_length=4000)
    published_at: datetime | None = None
    fetched_at: datetime
    freshness_status: FreshnessStatus
    trust_level: TrustLevel
    confidence: float = Field(..., ge=0, le=1)

    @model_validator(mode="after")
    def validate_source_identity(self) -> SourceEvidence:
        if self.url is None:
            if self.domain:
                raise ValueError("domain must be empty when url is unknown")
            if self.freshness_status != "unknown" or self.trust_level != "unknown":
                raise ValueError("missing sources must use unknown freshness and trust")
            if self.confidence != 0:
                raise ValueError("missing sources must have zero confidence")
            return self

        host = (urlsplit(str(self.url)).hostname or "").removeprefix("www.").lower()
        if self.domain.lower().removeprefix("www.") != host:
            raise ValueError("domain must match the evidence URL host")
        return self

    @classmethod
    def unknown(cls, query: ResearchQuery, *, fetched_at: datetime | None = None) -> SourceEvidence:
        """Represent an unanswered critical query without inventing a fact or source."""
        observed_at = fetched_at or datetime.now(timezone.utc)
        return cls(
            id=stable_research_id(str(query.id), "unknown"),
            title="Source unavailable",
            provider="fallback",
            claim_type=query.claim_type,
            claim_text=f"No verified source was found for: {query.query}",
            fetched_at=observed_at,
            freshness_status="unknown",
            trust_level="unknown",
            confidence=0,
        )


ProviderErrorCode = Literal[
    "authentication",
    "rate_limited",
    "timeout",
    "empty_results",
    "invalid_response",
    "unavailable",
]


class ProviderCallMetric(BaseModel):
    """Operational metadata for one provider attempt without request credentials."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(..., min_length=1, max_length=120)
    query_id: UUID
    latency_ms: int = Field(..., ge=0)
    success: bool
    error_code: ProviderErrorCode | None = None
    cache_hit: bool = False


class ProviderIssue(BaseModel):
    """Sanitized provider failure safe for checkpoints, logs, and API responses."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(..., min_length=1, max_length=120)
    query_id: UUID
    error_code: ProviderErrorCode
    message: str = Field(..., min_length=1, max_length=500)


class ResearchReport(BaseModel):
    """Serializable aggregate returned by research provider chains."""

    model_config = ConfigDict(extra="forbid")

    evidence: list[SourceEvidence] = Field(default_factory=list)
    issues: list[ProviderIssue] = Field(default_factory=list)
    metrics: list[ProviderCallMetric] = Field(default_factory=list)
    cache_hits: int = Field(default=0, ge=0)


class CommunityResearchResult(BaseModel):
    """Optional community context that can never fail the main planning flow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(..., min_length=1, max_length=120)
    status: Literal["available", "disabled", "empty", "unavailable"]
    context: str = Field(default="", max_length=20000)
    error_code: ProviderErrorCode | None = None
