"""High availability route-estimate providers."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from hashlib import sha256
from typing import Any

import httpx

from ...domain.trip_models import RouteEstimateV2
from .contracts import RouteEstimateProvider

AMAP_GEOCODE_ENDPOINT = "https://restapi.amap.com/v3/geocode/geo"
AMAP_DISTANCE_ENDPOINT = "https://restapi.amap.com/v3/distance"


def route_estimate_id(provider: str, origin: str, destination: str) -> str:
    digest = sha256(f"{provider}\0{origin}\0{destination}".encode()).hexdigest()[:20]
    return f"route-{digest}"


class NoopRouteEstimateProvider:
    """Return an explicit unavailable estimate when no map provider is configured."""

    name = "unavailable"

    def estimate(self, origin: str, destination: str) -> RouteEstimateV2:
        return RouteEstimateV2(
            estimate_id=route_estimate_id(self.name, origin, destination),
            origin=origin,
            destination=destination,
            provider=self.name,
            status="unavailable",
            detail="Route provider is not configured; verify distance and duration before booking.",
        )


class AmapRouteEstimateProvider:
    """Use AMap Web Service geocoding and distance APIs for planning estimates."""

    name = "amap"

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 10,
        client: httpx.Client | None = None,
    ) -> None:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        self._api_key = api_key.strip()
        self._timeout_seconds = timeout_seconds
        self._client = client

    def estimate(self, origin: str, destination: str) -> RouteEstimateV2:
        if not self._api_key:
            return NoopRouteEstimateProvider().estimate(origin, destination)

        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        owns_client = self._client is None
        try:
            origin_location = self._geocode(client, origin)
            destination_location = self._geocode(client, destination)
            if origin_location is None or destination_location is None:
                return self._unavailable(origin, destination, "AMap could not geocode both locations.")

            response = client.get(
                AMAP_DISTANCE_ENDPOINT,
                params={
                    "key": self._api_key,
                    "origins": origin_location,
                    "destination": destination_location,
                    "type": "1",
                    "output": "JSON",
                },
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", []) if payload.get("status") == "1" else []
            if not results:
                return self._unavailable(origin, destination, "AMap returned no route distance.")
            result = results[0]
            distance = self._non_negative_int(result.get("distance"))
            duration_seconds = self._non_negative_int(result.get("duration"))
            if distance is None:
                return self._unavailable(origin, destination, "AMap route distance was invalid.")
            return RouteEstimateV2(
                estimate_id=route_estimate_id(self.name, origin, destination),
                origin=origin,
                destination=destination,
                mode="driving",
                distance_meters=distance,
                duration_minutes=(duration_seconds + 59) // 60 if duration_seconds is not None else None,
                provider=self.name,
                status="verified",
                detail="Provider distance and driving-duration estimate; not a live transport schedule.",
            )
        except (httpx.HTTPError, TypeError, ValueError):
            return self._unavailable(origin, destination, "AMap route request was unavailable.")
        finally:
            if owns_client:
                client.close()

    def _geocode(self, client: httpx.Client, address: str) -> str | None:
        response = client.get(
            AMAP_GEOCODE_ENDPOINT,
            params={"key": self._api_key, "address": address, "output": "JSON"},
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        geocodes = payload.get("geocodes", []) if payload.get("status") == "1" else []
        if not geocodes:
            return None
        location = str(geocodes[0].get("location", ""))
        parts = location.split(",")
        if len(parts) != 2:
            return None
        float(parts[0])
        float(parts[1])
        return location

    @staticmethod
    def _non_negative_int(value: Any) -> int | None:
        try:
            parsed = int(float(value))
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    def _unavailable(self, origin: str, destination: str, detail: str) -> RouteEstimateV2:
        return RouteEstimateV2(
            estimate_id=route_estimate_id(self.name, origin, destination),
            origin=origin,
            destination=destination,
            provider=self.name,
            status="unavailable",
            detail=detail,
        )


class FallbackRouteEstimateProvider:
    """Try providers in order and preserve an explicit unavailable result."""

    name = "fallback"

    def __init__(self, providers: Sequence[RouteEstimateProvider]) -> None:
        self._providers = list(providers) or [NoopRouteEstimateProvider()]

    def estimate(self, origin: str, destination: str) -> RouteEstimateV2:
        last_result: RouteEstimateV2 | None = None
        for provider in self._providers:
            try:
                result = provider.estimate(origin, destination)
            except Exception:
                continue
            last_result = result
            if result.status != "unavailable":
                return result
        return last_result or NoopRouteEstimateProvider().estimate(origin, destination)


def build_route_estimate_provider(
    *,
    amap_api_key: str,
    timeout_seconds: float = 10,
    client: httpx.Client | None = None,
) -> FallbackRouteEstimateProvider:
    providers: list[RouteEstimateProvider]
    if amap_api_key.strip():
        providers = [
            AmapRouteEstimateProvider(
                amap_api_key,
                timeout_seconds=timeout_seconds,
                client=client,
            )
        ]
    else:
        providers = [NoopRouteEstimateProvider()]
    return FallbackRouteEstimateProvider(providers)
