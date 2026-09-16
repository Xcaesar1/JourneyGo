"""Provider-neutral travel research contracts and query generation."""

from .cache import MemoryResearchCache, NoopResearchCache, RedisResearchCache
from .community import (
    NoopCommunityResearchProvider,
    build_community_research_provider,
)
from .contracts import CommunityResearchProvider, ResearchCache, WebResearchProvider
from .factory import build_configured_web_research_provider
from .providers import (
    BraveSearchProvider,
    FallbackWebResearchProvider,
    NoopWebResearchProvider,
    build_web_research_provider,
)
from .queries import prepare_research_queries

__all__ = [
    "BraveSearchProvider",
    "CommunityResearchProvider",
    "FallbackWebResearchProvider",
    "MemoryResearchCache",
    "NoopResearchCache",
    "NoopCommunityResearchProvider",
    "NoopWebResearchProvider",
    "RedisResearchCache",
    "ResearchCache",
    "WebResearchProvider",
    "build_community_research_provider",
    "build_configured_web_research_provider",
    "build_web_research_provider",
    "prepare_research_queries",
]
