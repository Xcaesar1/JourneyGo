"""AMap-backed attraction discovery with deterministic ranking."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol

import httpx

from ..config import get_settings
from ..domain.attraction_models import (
    AttractionCandidate,
    AttractionCandidatePage,
    AttractionImage,
)
from ..domain.landmarks import discovery_queries, experience, metadata, same_experience
from .tripai_supplemental import (
    CtripWendaoSupplementalSource,
    SupplementalAttractionSource,
)

LOGGER = logging.getLogger(__name__)
AMAP_TEXT_SEARCH_URL = "https://restapi.amap.com/v5/place/text"
AMAP_DETAIL_URL = "https://restapi.amap.com/v5/place/detail"
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"

_INTEREST_QUERIES: dict[str, tuple[str, ...]] = {
    "历史文化": ("历史文化景点", "博物馆"),
    "history": ("历史文化景点", "博物馆"),
    "自然风光": ("自然风光", "公园"),
    "nature": ("自然风光", "公园"),
    "美食": ("特色街区", "美食街"),
    "food": ("特色街区", "美食街"),
    "购物": ("特色街区",),
    "shopping": ("特色街区",),
    "艺术": ("美术馆", "艺术馆"),
    "art": ("美术馆", "艺术馆"),
    "休闲": ("休闲景点", "公园"),
    "leisure": ("休闲景点", "公园"),
}

_PRIMARY_ATTRACTION_CATEGORIES = {
    "attraction",
    "科教文化服务",
    "风景名胜",
}
_LEISURE_INTERESTS = {"leisure", "休闲"}
_DISTRICT_INTERESTS = {"food", "shopping", "美食", "购物"}
_DISTRICT_CATEGORIES = {"购物服务", "餐饮服务"}
_DISTRICT_NAME_MARKERS = ("古城", "夜市", "小镇", "巷", "市场", "广场", "村", "街", "里")
_FACILITY_NAME_MARKERS = (
    "停车场",
    "公交站",
    "办公区",
    "卫生间",
    "商店",
    "售票处",
    "地铁站",
    "文创",
    "服务区",
    "游客中心",
    "管理区",
    "酒店",
)


class AttractionDiscoveryProvider(Protocol):
    def discover(
        self,
        city: str,
        *,
        interests: Sequence[str] = (),
        must_visit: Sequence[str] = (),
        avoid: Sequence[str] = (),
        days: int = 1,
        limit: int = 40,
    ) -> AttractionCandidatePage: ...


class NoopAttractionDiscoveryProvider:
    def discover(
        self,
        city: str,
        *,
        interests: Sequence[str] = (),
        must_visit: Sequence[str] = (),
        avoid: Sequence[str] = (),
        days: int = 1,
        limit: int = 40,
    ) -> AttractionCandidatePage:
        _ = interests, must_visit, avoid, days, limit
        return AttractionCandidatePage(
            city=city,
            items=[],
            total=0,
            degraded=True,
            issues=["amap_not_configured"],
        )


@dataclass(frozen=True)
class _RawCandidate:
    item: AttractionCandidate
    query_index: int
    result_index: int
    supplemental: bool = False


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _number(value: Any) -> float | None:
    try:
        text = str(value).strip()
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def _location(value: Any) -> tuple[float | None, float | None]:
    text = _text(value)
    if not text or "," not in text:
        return None, None
    longitude, latitude = text.split(",", 1)
    return _number(longitude), _number(latitude)


def _photo(raw: dict[str, Any]) -> AttractionImage:
    photos = raw.get("photos")
    if not isinstance(photos, list):
        return AttractionImage()
    for photo in photos:
        if isinstance(photo, dict) and _text(photo.get("url")):
            return AttractionImage(url=_text(photo["url"]), source="amap")
    return AttractionImage()


def _normalize_name(value: str) -> str:
    return re.sub(r"[\s·•()（）\[\]【】_-]+", "", value).casefold()


def _candidate_key(item: AttractionCandidate) -> str:
    return item.poi_id or f"{_normalize_name(item.name)}|{_normalize_name(item.address)}"


def _matches_suggested_name(item: AttractionCandidate, suggestion: str) -> bool:
    item_name = _normalize_name(item.name)
    suggested_name = _normalize_name(suggestion)
    return bool(
        item_name
        and suggested_name
        and (
            item_name == suggested_name
            or item_name in suggested_name
            or suggested_name in item_name
        )
        and item.longitude is not None
        and item.latitude is not None
    )


def _matches_any(item: AttractionCandidate, terms: Iterable[str]) -> bool:
    haystack = f"{item.name} {item.category} {item.address}".casefold()
    return any(term.strip().casefold() in haystack for term in terms if term.strip())


def _matched_interests(item: AttractionCandidate, interests: Sequence[str]) -> list[str]:
    matches: list[str] = []
    haystack = f"{item.name} {item.category}".casefold()
    for interest in interests:
        words = (interest, *_INTEREST_QUERIES.get(interest, ()))
        if any(word.casefold() in haystack for word in words if word):
            matches.append(interest)
    return list(dict.fromkeys(matches))


def _is_discoverable_attraction(
    item: AttractionCandidate,
    *,
    interests: Sequence[str],
    must_visit: Sequence[str],
) -> bool:
    """Reject AMap keyword-search noise while retaining explicit user choices."""
    if any(marker in item.name for marker in _FACILITY_NAME_MARKERS):
        return False
    normalized_name = _normalize_name(item.name)
    if any(
        _normalize_name(term) in normalized_name or normalized_name in _normalize_name(term)
        for term in must_visit
        if term.strip()
    ):
        return True
    category_root = item.category.split(";")[0].split("|")[0]
    if category_root in _PRIMARY_ATTRACTION_CATEGORIES:
        return True
    if category_root == "体育休闲服务":
        return any(interest in _LEISURE_INTERESTS for interest in interests)
    return (
        category_root in _DISTRICT_CATEGORIES
        and any(interest in _DISTRICT_INTERESTS for interest in interests)
        and any(marker in item.name for marker in _DISTRICT_NAME_MARKERS)
    )


def parse_amap_pois(payload: dict[str, Any], city: str) -> list[AttractionCandidate]:
    """Parse one AMap POI 2.0 payload without leaking provider-specific shapes."""
    if str(payload.get("status")) != "1":
        return []
    pois = payload.get("pois")
    if not isinstance(pois, list):
        return []
    parsed: list[AttractionCandidate] = []
    for raw in pois:
        if not isinstance(raw, dict):
            continue
        poi_id = _text(raw.get("id"))
        name = _text(raw.get("name"))
        if not poi_id or not name:
            continue
        business = raw.get("business") if isinstance(raw.get("business"), dict) else {}
        longitude, latitude = _location(raw.get("location"))
        parsed.append(
            AttractionCandidate(
                poi_id=poi_id,
                name=name,
                city=_text(raw.get("cityname")) or city,
                address=_text(raw.get("address")),
                longitude=longitude,
                latitude=latitude,
                category=_text(raw.get("type")) or "attraction",
                parent_poi_id=_text(raw.get("parent")),
                rating=_number(business.get("rating")),
                image=_photo(raw),
                **metadata(_text(raw.get("cityname")) or city, name),
            )
        )
    return parsed


def rank_amap_pois(
    payload: dict[str, Any], city: str, *, interests=(), must_visit=(), avoid=(), limit=25
):
    """Reuse homepage POI normalization and ranking for durable one-click evidence."""
    return rank_candidates(
        [
            _RawCandidate(item=item, query_index=0, result_index=index)
            for index, item in enumerate(parse_amap_pois(payload, city))
        ],
        interests=interests,
        must_visit=must_visit,
        avoid=avoid,
        limit=limit,
    )


def rank_candidates(
    raw_candidates: Sequence[_RawCandidate],
    *,
    interests: Sequence[str],
    must_visit: Sequence[str],
    avoid: Sequence[str],
    limit: int,
) -> list[AttractionCandidate]:
    """Deduplicate and score candidates using provider order, rating and diversity."""
    deduplicated: dict[str, _RawCandidate] = {}
    parents = {raw.item.poi_id: raw.item for raw in raw_candidates if raw.item.is_landmark}
    resolved = []
    for raw in raw_candidates:
        parent = parents.get(raw.item.parent_poi_id)
        if parent and not raw.item.experience_group and parent.city.removesuffix("市") == raw.item.city.removesuffix("市"):
            raw = replace(raw, item=raw.item.model_copy(update={
                **metadata(parent.city, parent.name),
                "experience_aliases": [*parent.experience_aliases, raw.item.name],
            }))
        resolved.append(raw)
    raw_candidates = resolved
    supplemental_keys = {_candidate_key(raw.item) for raw in raw_candidates if raw.supplemental}
    for raw in raw_candidates:
        if _matches_any(raw.item, avoid) or any(same_experience(raw.item.city, raw.item.name, name) for name in avoid):
            continue
        if not _is_discoverable_attraction(
            raw.item,
            interests=interests,
            must_visit=must_visit,
        ):
            continue
        key = _candidate_key(raw.item)
        existing = deduplicated.get(key)
        if existing is None or (raw.query_index, raw.result_index) < (
            existing.query_index,
            existing.result_index,
        ):
            deduplicated[key] = raw

    scored: list[tuple[float, _RawCandidate, list[str], bool]] = []
    must_visit_winners: set[str] = set()
    for term in must_visit:
        normalized_term = _normalize_name(term)
        if not normalized_term:
            continue
        matches = [
            raw
            for raw in deduplicated.values()
            if normalized_term in _normalize_name(raw.item.name)
            or _normalize_name(raw.item.name) in normalized_term
        ]
        if not matches:
            continue
        winner = max(
            matches,
            key=lambda raw: (
                _normalize_name(raw.item.name) == normalized_term,
                -raw.query_index,
                raw.item.rating or 0,
                -raw.result_index,
            ),
        )
        must_visit_winners.add(_candidate_key(winner.item))
    for raw in deduplicated.values():
        matches = _matched_interests(raw.item, interests)
        is_must_visit = _candidate_key(raw.item) in must_visit_winners
        provider_score = max(0.0, 42.0 - raw.query_index * 4.0 - raw.result_index * 0.8)
        rating_score = (raw.item.rating or 0) / 5 * 28
        interest_score = min(18.0, len(matches) * 9.0)
        must_visit_score = 40.0 if is_must_visit else 0.0
        scored.append(
            (
                provider_score + rating_score + interest_score + must_visit_score,
                raw,
                matches,
                is_must_visit,
            )
        )

    scored.sort(
        key=lambda entry: (
            -entry[0],
            entry[1].query_index,
            entry[1].result_index,
            entry[1].item.name,
        )
    )
    category_counts: dict[str, int] = {}
    seen_groups = set()
    ranked: list[AttractionCandidate] = []
    remaining = list(scored)
    while remaining and len(ranked) < max(1, min(limit, 40)):

        def adjusted(entry: tuple[float, _RawCandidate, list[str], bool]) -> float:
            category = entry[1].item.category.split(";")[0].split("|")[0]
            return entry[0] - min(category_counts.get(category, 0) * 3.0, 15.0)

        best_index = max(
            range(len(remaining)),
            key=lambda index: (
                remaining[index][3],
                remaining[index][1].item.is_landmark,
                bool(remaining[index][2]),
                adjusted(remaining[index]),
                -remaining[index][1].query_index,
                -remaining[index][1].result_index,
            ),
        )
        base_score, raw, matches, is_must_visit = remaining.pop(best_index)
        group = raw.item.experience_group
        if group and group in seen_groups:
            continue
        if group:
            # Prefer a concrete canonical place over a broad district/alias.
            rule = experience(raw.item.city, raw.item.name)
            canonical = next((entry for entry in remaining if entry[1].item.experience_group == group and (entry[1].item.name == rule["name"] if rule else entry[1].item.poi_id == raw.item.parent_poi_id)), None)
            if canonical and not is_must_visit:
                remaining.remove(canonical)
                base_score, raw, matches, is_must_visit = canonical
            seen_groups.add(group)
        category_root = raw.item.category.split(";")[0].split("|")[0]
        diversity_penalty = min(category_counts.get(category_root, 0) * 3.0, 15.0)
        score = min(100.0, max(0.0, base_score - diversity_penalty))
        category_counts[category_root] = category_counts.get(category_root, 0) + 1
        reasons = []
        if is_must_visit:
            reasons.append("用户指定必去")
        if matches:
            reasons.append("匹配" + "、".join(matches))
        if raw.item.rating:
            reasons.append(f"高德评分 {raw.item.rating:.1f}")
        if not reasons:
            reasons.append("高德检索与评分综合推荐（非热度榜）")
        if raw.item.is_landmark:
            reasons.insert(0, "城市代表景点")
        if _candidate_key(raw.item) in supplemental_keys:
            reasons.append("携程问道补充推荐（高德已验证）")
        ranked.append(
            raw.item.model_copy(
                update={
                    "recommendation_score": round(score, 2),
                    "recommendation_reason": "；".join(reasons),
                    "matched_interests": matches,
                    "is_must_visit": is_must_visit,
                }
            )
        )
    return ranked


class AmapAttractionDiscoveryProvider:
    """Direct AMap REST provider; route/weather MCP use remains separate."""

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10,
        supplemental_source: SupplementalAttractionSource | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("AMap Web service key is required.")
        self._api_key = api_key.strip()
        self._client = client or httpx.Client(timeout=timeout)
        self._supplemental_source = supplemental_source

    def _search_page(self, city: str, keywords: str, page_num: int) -> dict[str, Any]:
        response = self._client.get(
            AMAP_TEXT_SEARCH_URL,
            params={
                "key": self._api_key,
                "keywords": keywords,
                "region": city,
                "city_limit": "true",
                "show_fields": "business,photos",
                "page_size": 25,
                "page_num": page_num,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("AMap returned a non-object payload.")
        return payload

    def get_detail(self, poi_id: str) -> AttractionCandidate | None:
        response = self._client.get(
            AMAP_DETAIL_URL,
            params={"key": self._api_key, "id": poi_id, "show_fields": "business,photos"},
        )
        response.raise_for_status()
        payload = response.json()
        items = parse_amap_pois(payload, "")
        return items[0] if items else None

    def geocode(self, address: str, city: str = "") -> tuple[float, float] | None:
        response = self._client.get(
            AMAP_GEOCODE_URL,
            params={"key": self._api_key, "address": address, "city": city},
        )
        response.raise_for_status()
        payload = response.json()
        geocodes = payload.get("geocodes") if isinstance(payload, dict) else None
        if str(payload.get("status")) != "1" or not isinstance(geocodes, list) or not geocodes:
            return None
        longitude, latitude = _location(geocodes[0].get("location"))
        if longitude is None or latitude is None:
            return None
        return longitude, latitude

    def discover(
        self,
        city: str,
        *,
        interests: Sequence[str] = (),
        must_visit: Sequence[str] = (),
        avoid: Sequence[str] = (),
        days: int = 1,
        limit: int = 40,
    ) -> AttractionCandidatePage:
        normalized_city = city.strip()
        supplemental_names: tuple[str, ...] = ()
        supplemental_issues: list[str] = []
        if self._supplemental_source is not None:
            supplemental = self._supplemental_source.recommend(
                normalized_city,
                interests=tuple(interests),
                limit=6,
            )
            supplemental_names = supplemental.names
            if supplemental.issue:
                supplemental_issues.append(supplemental.issue)
        query_terms = discovery_queries(normalized_city, interests, must_visit)
        raw_candidates: list[_RawCandidate] = []
        searched_pages: dict[str, list[AttractionCandidate]] = {}
        primary_issues: list[str] = []
        for query_index, keywords in enumerate(query_terms):
            for page_num in (1, 2):
                try:
                    payload = self._search_page(normalized_city, keywords, page_num)
                    page = parse_amap_pois(payload, normalized_city)
                    searched_pages.setdefault(keywords, []).extend(page)
                    for result_index, item in enumerate(page):
                        raw_candidates.append(
                            _RawCandidate(item, query_index, (page_num - 1) * 25 + result_index)
                        )
                    if len(page) < 25:
                        break
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    LOGGER.warning(
                        "AMap attraction discovery degraded for city=%s error=%s",
                        normalized_city,
                        type(exc).__name__,
                    )
                    primary_issues.append("amap_request_failed")
                    break

        supplemental_query_index = len(query_terms)
        for offset, suggestion in enumerate(supplemental_names):
            try:
                verified = searched_pages.get(suggestion)
                if verified is None:
                    payload = self._search_page(normalized_city, suggestion, 1)
                    verified = parse_amap_pois(payload, normalized_city)
                matches = [
                    item
                    for item in verified
                    if _matches_suggested_name(item, suggestion)
                ]
                if not matches:
                    continue
                winner = max(
                    matches,
                    key=lambda item: (
                        _normalize_name(item.name) == _normalize_name(suggestion),
                        item.rating or 0,
                    ),
                )
                raw_candidates.append(
                    _RawCandidate(
                        winner,
                        supplemental_query_index + offset,
                        0,
                        supplemental=True,
                    )
                )
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                LOGGER.warning(
                    "AMap validation of TripAI suggestion failed city=%s error=%s",
                    normalized_city,
                    type(exc).__name__,
                )
                supplemental_issues.append("tripai_amap_validation_failed")
        items = rank_candidates(
            raw_candidates,
            interests=interests,
            must_visit=must_visit,
            avoid=avoid,
            limit=limit,
        )
        default_count = min(len(items), max(2, min(days * 2, 10)))
        required_ids = [item.poi_id for item in items if item.is_must_visit]
        preferred_items = [
            item
            for item in items
            if any(interest in {"nature", "自然风光"} for interest in interests)
            and item.category.startswith("风景名胜")
        ]
        default_source = [item for item in items if item.is_landmark] + preferred_items + items
        default_pool = list(dict.fromkeys(item.poi_id for item in default_source))
        defaults = list(dict.fromkeys(required_ids + default_pool))[
            : max(default_count, len(required_ids))
        ]
        return AttractionCandidatePage(
            city=normalized_city,
            items=items,
            total=len(items),
            default_selected_ids=defaults,
            degraded=bool(primary_issues) or not items,
            issues=list(
                dict.fromkeys(
                    primary_issues + supplemental_issues + (["no_candidates"] if not items else [])
                )
            ),
        )


def build_configured_attraction_discovery_provider() -> AttractionDiscoveryProvider:
    settings = get_settings()
    if not settings.vite_amap_web_key.strip():
        return NoopAttractionDiscoveryProvider()
    supplemental_source = None
    tripai_api_key = settings.tripai_api_key.get_secret_value()
    if settings.tripai_enabled and tripai_api_key:
        supplemental_source = CtripWendaoSupplementalSource(
            tripai_api_key,
            base_url=settings.tripai_base_url,
            timeout=settings.tripai_timeout,
        )
    return AmapAttractionDiscoveryProvider(
        settings.vite_amap_web_key,
        supplemental_source=supplemental_source,
    )
