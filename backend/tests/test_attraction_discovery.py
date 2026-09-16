"""Attraction discovery, ranking, image fallback, and provider isolation tests."""

from __future__ import annotations

from collections import Counter

import httpx
from backend.app.domain.attraction_models import AttractionCandidate, AttractionImage
from backend.app.services.attraction_discovery import (
    AmapAttractionDiscoveryProvider,
    parse_amap_pois,
)
from backend.app.services.attraction_images import AttractionImageService
from backend.app.services.research.community import (
    NoopCommunityResearchProvider,
    build_community_research_provider,
)


def _poi(
    poi_id: str,
    name: str,
    *,
    category: str = "风景名胜;公园广场",
    rating: str = "4.6",
    photo: str = "https://example.test/image.jpg",
) -> dict:
    return {
        "id": poi_id,
        "name": name,
        "cityname": "北京",
        "address": "测试地址",
        "location": "116.397,39.908",
        "type": category,
        "business": {"rating": rating},
        "photos": [{"url": photo}] if photo else [],
    }


def test_parse_amap_pois_preserves_photo_rating_and_coordinates() -> None:
    items = parse_amap_pois({"status": "1", "pois": [_poi("A1", "故宫博物院")]}, "北京")

    assert len(items) == 1
    assert items[0].image.url == "https://example.test/image.jpg"
    assert items[0].image.source == "amap"
    assert items[0].rating == 4.6
    assert items[0].longitude == 116.397
    assert items[0].latitude == 39.908


def test_amap_discovery_paginates_deduplicates_and_caps_results() -> None:
    calls: Counter[int] = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        page_num = int(request.url.params["page_num"])
        calls[page_num] += 1
        start = 0 if page_num == 1 else 25
        size = 25 if page_num == 1 else 20
        pois = [_poi(f"P{index}", f"景点 {index}") for index in range(start, start + size)]
        return httpx.Response(200, json={"status": "1", "pois": pois})

    provider = AmapAttractionDiscoveryProvider(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    page = provider.discover("北京", interests=["历史文化"], days=3, limit=40)

    assert calls[2] > 0
    assert page.total == 40
    assert len({item.poi_id for item in page.items}) == 40
    assert len(page.default_selected_ids) == 6


def test_amap_discovery_prioritizes_must_visit_and_filters_avoid_terms() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["page_num"] == "2":
            return httpx.Response(200, json={"status": "1", "pois": []})
        return httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    _poi("A1", "故宫博物院", category="科教文化服务;博物馆"),
                    _poi("A4", "故宫博物院-午门", category="风景名胜;旅游景点"),
                    _poi("A2", "避开商业街", category="购物服务"),
                    _poi("A3", "北海公园", category="风景名胜;公园广场", rating="4.8"),
                ],
            },
        )

    provider = AmapAttractionDiscoveryProvider(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    page = provider.discover(
        "北京",
        interests=["历史文化", "自然风光"],
        must_visit=["故宫"],
        avoid=["商业街"],
        limit=10,
    )

    assert page.items[0].name == "故宫博物院"
    assert page.items[0].is_must_visit is True
    assert "历史文化" in page.items[0].matched_interests
    assert all("商业街" not in item.name for item in page.items)
    assert [item.name for item in page.items if item.is_must_visit] == ["故宫博物院"]


def test_amap_discovery_filters_keyword_noise_and_keeps_explicit_must_visit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["page_num"] == "2":
            return httpx.Response(200, json={"status": "1", "pois": []})
        return httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    _poi("A1", "西安城墙"),
                    _poi("A2", "景区游客中心"),
                    _poi("A3", "安特大世界", category="购物服务;专卖店"),
                    _poi("A4", "用户指定咖啡店", category="餐饮服务;咖啡厅"),
                    _poi("A5", "城市运动馆", category="体育休闲服务;运动场馆"),
                ],
            },
        )

    provider = AmapAttractionDiscoveryProvider(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    page = provider.discover("西安", must_visit=["用户指定咖啡店"], limit=10)

    assert [item.name for item in page.items] == ["用户指定咖啡店", "西安城墙"]


def test_nature_defaults_prefer_scenic_candidates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["page_num"] == "2":
            return httpx.Response(200, json={"status": "1", "pois": []})
        return httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    _poi("M1", "热门博物馆", category="科教文化服务;博物馆"),
                    _poi("N1", "西湖", category="风景名胜;风景名胜"),
                    _poi("N2", "西溪湿地", category="风景名胜;公园广场"),
                ],
            },
        )

    provider = AmapAttractionDiscoveryProvider(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    page = provider.discover("杭州", interests=["自然风光"], days=1)

    assert set(page.default_selected_ids) == {"N1", "N2"}
    assert "M1" not in page.default_selected_ids


def test_amap_discovery_uses_city_popularity_queries_before_interest_queries() -> None:
    keywords: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        keywords.append(request.url.params["keywords"])
        return httpx.Response(200, json={"status": "1", "pois": []})

    provider = AmapAttractionDiscoveryProvider(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    provider.discover("西安", interests=["历史文化"])

    assert keywords[:2] == ["西安5A景区", "西安必游景点"]
    assert "西安博物馆" in keywords


class _AmapWithPhoto:
    def get_detail(self, _poi_id: str) -> AttractionCandidate:
        return AttractionCandidate(
            poi_id="A1",
            name="故宫博物院",
            city="北京",
            image=AttractionImage(url="https://amap.test/photo.jpg", source="amap"),
        )


async def test_image_resolution_prefers_amap_photo() -> None:
    service = AttractionImageService(amap_provider=_AmapWithPhoto())  # type: ignore[arg-type]

    image = await service.resolve(poi_id="A1", name="故宫博物院", city="北京")

    assert image.source == "amap"
    assert image.url == "https://amap.test/photo.jpg"


async def test_image_resolution_uses_allowed_openverse_license_and_attribution() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {"url": "https://blocked.test/image.jpg", "license": "nc"},
                    {
                        "thumbnail": "https://openverse.test/image.jpg",
                        "creator": "Example Author",
                        "license": "by-sa",
                        "license_version": "4.0",
                        "foreign_landing_url": "https://source.test/work",
                    },
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = AttractionImageService(client=client)
        image = await service.resolve(name="西湖", city="杭州")

    assert image.source == "openverse"
    assert image.license == "BY-SA 4.0"
    assert image.author == "Example Author"
    assert image.source_page == "https://source.test/work"
    assert "Example Author" in image.attribution


async def test_image_resolution_returns_placeholder_when_all_providers_are_empty() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"results": []}))
    ) as client:
        image = await AttractionImageService(client=client).resolve(name="无结果", city="测试")

    assert image.source == "placeholder"
    assert image.url == ""


def test_normal_provider_builder_never_enables_xhs() -> None:
    assert isinstance(build_community_research_provider(), NoopCommunityResearchProvider)
