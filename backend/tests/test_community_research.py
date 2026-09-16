"""Optional community-provider behavior and redaction tests."""

from __future__ import annotations

from backend.app.services.research.community import (
    NoopCommunityResearchProvider,
    build_community_research_provider,
)


async def test_disabled_community_provider_returns_safe_context() -> None:
    result = await NoopCommunityResearchProvider().research("Tokyo", "food", "en")

    assert result.status == "disabled"
    assert "official sources" in result.context


def test_configured_community_provider_is_always_disabled() -> None:
    assert isinstance(build_community_research_provider(), NoopCommunityResearchProvider)
