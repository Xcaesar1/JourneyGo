"""Route estimation provider exports."""

from ...config import get_settings
from .contracts import RouteEstimateProvider
from .providers import (
    AmapRouteEstimateProvider,
    FallbackRouteEstimateProvider,
    NoopRouteEstimateProvider,
    build_route_estimate_provider,
)


def build_configured_route_estimate_provider() -> FallbackRouteEstimateProvider:
    settings = get_settings()
    return build_route_estimate_provider(amap_api_key=settings.vite_amap_web_key)


__all__ = [
    "AmapRouteEstimateProvider",
    "FallbackRouteEstimateProvider",
    "NoopRouteEstimateProvider",
    "RouteEstimateProvider",
    "build_configured_route_estimate_provider",
    "build_route_estimate_provider",
]
