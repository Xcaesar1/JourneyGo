"""AMap and Openverse image resolution with metadata-only caching."""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from redis import Redis
from redis.exceptions import RedisError

from ..domain.attraction_models import AttractionImage
from .attraction_discovery import AmapAttractionDiscoveryProvider
from .task_events import redis_url

LOGGER = logging.getLogger(__name__)
OPENVERSE_IMAGES_URL = "https://api.openverse.org/v1/images/"
ALLOWED_OPENVERSE_LICENSES = {"cc0", "pdm", "by", "by-sa"}


class AttractionImageService:
    """Resolve remote image metadata without downloading third-party content."""

    def __init__(
        self,
        *,
        amap_provider: AmapAttractionDiscoveryProvider | None = None,
        client: httpx.AsyncClient | None = None,
        cache: Redis | None = None,
        cache_ttl_seconds: int = 86400,
    ) -> None:
        self._amap_provider = amap_provider
        self._client = client or httpx.AsyncClient(timeout=10, follow_redirects=True)
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    @staticmethod
    def _cache_key(poi_id: str, name: str, city: str) -> str:
        readable = "-".join(part.strip() for part in (poi_id, city, name) if part.strip())
        safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", readable).strip("-")
        return f"journeyops:attraction-image:v1:{safe[:180] or 'unknown'}"

    async def _cache_get(self, key: str) -> AttractionImage | None:
        if self._cache is None:
            return None
        try:
            payload = await asyncio.to_thread(self._cache.get, key)
            if payload:
                return AttractionImage.model_validate_json(payload)
        except (RedisError, ValueError, TypeError):
            return None
        return None

    async def _cache_set(self, key: str, image: AttractionImage) -> None:
        if self._cache is None:
            return
        try:
            await asyncio.to_thread(
                self._cache.set,
                key,
                image.model_dump_json(),
                ex=self._cache_ttl_seconds,
            )
        except RedisError:
            LOGGER.info("Attraction image metadata cache unavailable.")

    async def _from_amap(self, poi_id: str) -> AttractionImage | None:
        if not poi_id or self._amap_provider is None:
            return None
        try:
            candidate = await asyncio.to_thread(self._amap_provider.get_detail, poi_id)
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        if candidate and candidate.image.url:
            return candidate.image
        return None

    async def _from_openverse(self, name: str, city: str) -> AttractionImage | None:
        query = " ".join(part for part in (name.strip(), city.strip()) if part)
        if not query:
            return None
        try:
            response = await self._client.get(
                OPENVERSE_IMAGES_URL,
                params={
                    "q": query,
                    "license": "cc0,pdm,by,by-sa",
                    "page_size": 10,
                    "mature": "false",
                },
                headers={"User-Agent": "JourneyOps/2.0 attraction-image-resolver"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            return None
        for raw in results:
            if not isinstance(raw, dict):
                continue
            license_code = str(raw.get("license") or "").strip().lower()
            url = str(raw.get("thumbnail") or raw.get("url") or "").strip()
            if license_code not in ALLOWED_OPENVERSE_LICENSES or not url:
                continue
            author = str(raw.get("creator") or "").strip()
            source_page = str(raw.get("foreign_landing_url") or "").strip()
            license_version = str(raw.get("license_version") or "").strip()
            license_label = " ".join(
                part for part in (license_code.upper(), license_version) if part
            )
            attribution = str(raw.get("attribution") or "").strip()
            if not attribution:
                attribution = f"{author or 'Unknown author'} · {license_label} · Openverse"
            return AttractionImage(
                url=url,
                source="openverse",
                author=author,
                license=license_label,
                source_page=source_page,
                attribution=attribution,
            )
        return None

    async def resolve(self, *, poi_id: str = "", name: str, city: str = "") -> AttractionImage:
        key = self._cache_key(poi_id, name, city)
        cached = await self._cache_get(key)
        if cached is not None:
            return cached
        image = await self._from_amap(poi_id)
        if image is None:
            image = await self._from_openverse(name, city)
        if image is None:
            image = AttractionImage()
        await self._cache_set(key, image)
        return image


def build_attraction_image_service(
    amap_provider: AmapAttractionDiscoveryProvider | None,
) -> AttractionImageService:
    try:
        cache = Redis.from_url(
            redis_url(),
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    except (RedisError, ValueError):
        cache = None
    return AttractionImageService(amap_provider=amap_provider, cache=cache)
