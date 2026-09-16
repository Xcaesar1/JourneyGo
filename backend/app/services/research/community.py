"""Optional Xiaohongshu community provider with failure isolation."""

from __future__ import annotations

from ...domain.research_models import CommunityResearchResult


def _fallback_context(language: str) -> str:
    normalized = language.lower().split("-", 1)[0]
    if normalized == "zh":
        return "社区体验来源不可用；请仅使用地图、官方来源和通用建议。"
    if normalized == "ja":
        return (
            "コミュニティ情報は利用できません。地図、公式情報、一般的な提案のみを使用してください。"
        )
    return (
        "Community insights are unavailable; use maps, official sources, and general guidance only."
    )


class NoopCommunityResearchProvider:
    name = "community_noop"

    async def research(
        self,
        city: str,
        keywords: str,
        language: str,
    ) -> CommunityResearchResult:
        _ = city, keywords
        return CommunityResearchResult(
            provider=self.name,
            status="disabled",
            context=_fallback_context(language),
        )


def build_community_research_provider():
    """Community scraping is intentionally disabled for every runtime path."""
    return NoopCommunityResearchProvider()
