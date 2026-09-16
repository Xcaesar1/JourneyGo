"""Regression tests for browser-safe runtime configuration status."""

from __future__ import annotations

from backend.app.api.routes import settings as settings_routes
from backend.app.config import settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(settings_routes.router, prefix="/api")
    return TestClient(app)


def test_runtime_settings_get_never_serializes_backend_secrets(monkeypatch) -> None:
    secret_values = {
        "openai_api_key": "llm-secret-test-value",
        "vite_amap_web_key": "amap-secret-test-value",
        "google_maps_api_key": "google-secret-test-value",
        "xhs_cookie": "xhs-secret-test-value",
    }
    for field, value in secret_values.items():
        monkeypatch.setattr(settings, field, value)
    monkeypatch.setattr(settings, "xhs_enabled", True)

    with _client() as client:
        response = client.get("/api/settings")

    assert response.status_code == 200
    serialized = response.text
    assert all(value not in serialized for value in secret_values.values())
    assert response.json()["data"]["llm_configured"] is True
    assert "xhs_configured" not in response.json()["data"]


def test_runtime_settings_exposes_only_domain_restricted_browser_map_credentials(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "vite_amap_web_js_key", "browser-map-key")
    monkeypatch.setattr(settings, "vite_amap_security_js_code", "browser-security-code")

    with _client() as client:
        response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["data"]["vite_amap_web_js_key"] == "browser-map-key"
    assert response.json()["data"]["vite_amap_security_js_code"] == "browser-security-code"


def test_runtime_secret_updates_are_disabled_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "runtime_secret_updates_enabled", False)

    with _client() as client:
        response = client.put("/api/settings", json={"openai_api_key": "new-secret"})

    assert response.status_code == 403


def test_runtime_secret_updates_require_access_code_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "runtime_secret_updates_enabled", True)
    monkeypatch.setattr(settings, "api_access_code", SecretStr("admin-test-code"))

    with _client() as client:
        response = client.put("/api/settings", json={"openai_api_key": "new-secret"})

    assert response.status_code == 401
