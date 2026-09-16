"""Ctrip Wendao supplementary attraction source tests."""

from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

import httpx
from backend.app.services import attraction_discovery
from backend.app.services.attraction_discovery import (
    AmapAttractionDiscoveryProvider,
    build_configured_attraction_discovery_provider,
)
from backend.app.services.tripai_supplemental import (
    CtripWendaoSupplementalSource,
    SupplementalAttractionResult,
    parse_tripai_attraction_names,
)
from pydantic import SecretStr


def _poi(poi_id: str, name: str, *, location: str = "116.397,39.908") -> dict:
    return {
        "id": poi_id,
        "name": name,
        "cityname": "北京",
        "address": "测试地址",
        "location": location,
        "type": "风景名胜;旅游景点",
        "business": {"rating": "4.8"},
        "photos": [{"url": "https://amap.test/photo.jpg"}],
    }


def test_parse_tripai_markdown_ignores_prose_and_deduplicates() -> None:
    payload = "- **故宫博物院**\n- [天坛公园](https://example.test)\n- 故宫博物院\n有需要随时找我～"

    assert parse_tripai_attraction_names(payload) == ["故宫博物院", "天坛公园"]


def test_parse_tripai_table_and_reject_malformed_response() -> None:
    table = "| 序号 | 景点 |\n| --- | --- |\n| 1 | 颐和园 |\n| 2 | 北海公园 |"

    assert parse_tripai_attraction_names(table) == ["颐和园", "北海公园"]
    assert parse_tripai_attraction_names("建议先去故宫，然后去天坛。") == []


def test_wendao_source_calls_once_and_sends_token_without_logging_it() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.method == "POST"
        assert b'"token":"secret-token"' in request.content
        return httpx.Response(200, json="- 故宫博物院\n- 天坛公园")

    source = CtripWendaoSupplementalSource(
        "secret-token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = source.recommend("北京", interests=("历史文化",))

    assert calls == 1
    assert result == SupplementalAttractionResult(names=("故宫博物院", "天坛公园"))


def test_wendao_source_degrades_on_rate_limit_and_invalid_markdown() -> None:
    rate_limited = CtripWendaoSupplementalSource(
        "test-token",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(429))
        ),
    )
    invalid = CtripWendaoSupplementalSource(
        "test-token",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json={"unexpected": "shape"})
            )
        ),
    )

    assert rate_limited.recommend("北京").issue == "tripai_rate_limited"
    assert invalid.recommend("北京").issue == "tripai_invalid_response"


def test_wendao_source_degrades_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    source = CtripWendaoSupplementalSource(
        "test-token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert source.recommend("北京").issue == "tripai_request_failed"


def test_configured_builder_keeps_tripai_disabled_without_feature_flag(monkeypatch) -> None:
    configured = SimpleNamespace(
        vite_amap_web_key="amap-key",
        tripai_enabled=False,
        tripai_api_key=SecretStr("tripai-key"),
        tripai_base_url="https://wendao.test/skill/query",
        tripai_timeout=30,
    )
    monkeypatch.setattr(attraction_discovery, "get_settings", lambda: configured)

    provider = build_configured_attraction_discovery_provider()

    assert isinstance(provider, AmapAttractionDiscoveryProvider)
    assert provider._supplemental_source is None


class _SupplementalSource:
    def __init__(self, result: SupplementalAttractionResult) -> None:
        self.result = result
        self.calls: Counter[str] = Counter()

    def recommend(
        self,
        city: str,
        *,
        interests: tuple[str, ...] = (),
        limit: int = 6,
    ) -> SupplementalAttractionResult:
        _ = interests, limit
        self.calls[city] += 1
        return self.result


def test_amap_validates_each_supplement_and_rejects_unmatched_or_missing_coordinates() -> None:
    source = _SupplementalSource(
        SupplementalAttractionResult(names=("故宫博物院", "虚构景点", "无坐标公园"))
    )
    amap_queries: Counter[str] = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        keyword = request.url.params["keywords"]
        amap_queries[keyword] += 1
        if keyword == "故宫博物院":
            pois = [_poi("T1", "故宫博物院")]
        elif keyword == "虚构景点":
            pois = [_poi("T2", "完全不同的真实景点")]
        elif keyword == "无坐标公园":
            pois = [_poi("T3", "无坐标公园", location="")]
        else:
            pois = [_poi("B1", "高德基础景点")]
        return httpx.Response(200, json={"status": "1", "pois": pois})

    provider = AmapAttractionDiscoveryProvider(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        supplemental_source=source,
    )
    page = provider.discover("北京")

    assert source.calls == Counter({"北京": 1})
    assert amap_queries["故宫博物院"] == 1
    assert amap_queries["虚构景点"] == 1
    assert amap_queries["无坐标公园"] == 1
    names = {item.name for item in page.items}
    assert "故宫博物院" in names
    assert "完全不同的真实景点" not in names
    assert "无坐标公园" not in names
    verified = next(item for item in page.items if item.name == "故宫博物院")
    assert "高德已验证" in verified.recommendation_reason
    assert verified.image.source == "amap"


def test_supplement_failure_does_not_degrade_successful_amap_results() -> None:
    source = _SupplementalSource(SupplementalAttractionResult(issue="tripai_request_failed"))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "1", "pois": [_poi("B1", "高德基础景点")]})

    provider = AmapAttractionDiscoveryProvider(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        supplemental_source=source,
    )
    page = provider.discover("北京")

    assert page.total == 1
    assert page.degraded is False
    assert page.issues == ["tripai_request_failed"]
