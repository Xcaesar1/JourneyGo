import pytest
from backend.app.api.v2.tasks import PersonalMapInput
from backend.app.config import Settings
from backend.app.db.models import Trip, TripTask, TripVersion
from backend.app.services.personal_map import export_map, map_lines, safe_map_url
from fastapi import HTTPException
from pydantic import ValidationError


def place(name, id):
    return {"name": name, "poi_id": id, "location": {"longitude": 108.9, "latitude": 34.2}}


def plan():
    return {
        "city": "西安",
        "days": [
            {
                "date": "2026-09-30",
                "attractions": [place("城墙", "B001"), {"name": "未知景点"}],
                "meals": [place("餐厅", "B002")],
                "timeline": [{"start": "12:00", "reference_name": "餐厅"}],
                "hotel": place("酒店", "B003"),
            }
        ],
    }


def test_order_dedup_and_omission():
    lines, omitted = map_lines(plan())
    assert [p["name"] for p in lines[0]["pointInfoList"]] == ["餐厅", "城墙", "酒店"]
    assert omitted == ["未知景点"]
    with pytest.raises(HTTPException):
        map_lines(plan(), 1)
    with pytest.raises(HTTPException):
        map_lines({"days": []})


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://amap.com.evil.test/x",
        "https://evil.test/x",
        "https://user@surl.amap.com/x",
        "amapuri://other/action",
    ],
)
def test_reject_external_links(url):
    assert not safe_map_url(url)


def test_require_consent_and_exact_snapshot():
    for payload in (
        {"version": 1},
        {"confirmed": True},
        {"version": 1, "review_id": "r", "confirmed": True},
    ):
        with pytest.raises(ValidationError):
            PersonalMapInput(**payload)


def test_credentials_redacted_in_http_logs():
    import logging

    from backend.app.services.personal_map import _HideMcpCredentials
    record = logging.LogRecord("httpx", 20, "", 1, 'POST https://mcp.amap.com/mcp?key=secret-value HTTP/1.1', (), None)
    assert _HideMcpCredentials().filter(record)
    assert 'secret-value' not in record.getMessage()


def seed(session):
    session.add(Trip(id="t", idempotency_key="k", request_payload={}))
    session.flush()
    session.add(TripTask(id="task", trip_id="t"))
    session.add(TripVersion(trip_id="t", version=1, payload={}, native_payload=plan()))
    session.commit()


@pytest.mark.asyncio
async def test_durable_reuse_and_concurrent_click(db_session_factory):
    calls = []
    settings = Settings(_env_file=None, amap_personal_map_enabled=True, vite_amap_web_key="fake")
    payload = PersonalMapInput(version=1, confirmed=True)

    async def provider(*_):
        calls.append(1)
        with db_session_factory() as other:
            with pytest.raises(HTTPException) as conflict:
                await export_map(other, settings, "task", payload, provider)
            assert conflict.value.status_code == 409
        return "https://surl.amap.com/test-fixture"

    with db_session_factory() as session:
        seed(session)
        result = await export_map(session, settings, "task", payload, provider)
    with db_session_factory() as session:
        assert await export_map(session, settings, "task", payload, provider) == result
    assert calls == [1]


@pytest.mark.asyncio
async def test_timeout_not_resent_and_disabled_not_sent(db_session_factory):
    settings = Settings(_env_file=None, amap_personal_map_enabled=False, vite_amap_web_key="fake")
    payload = PersonalMapInput(version=1, confirmed=True)
    calls = []

    async def provider(*_):
        calls.append(1)
        raise TimeoutError()

    with db_session_factory() as session:
        seed(session)
        with pytest.raises(HTTPException) as disabled:
            await export_map(session, settings, "task", payload, provider)
        assert disabled.value.status_code == 503 and calls == []
        settings.amap_personal_map_enabled = True
        for _ in range(2):
            with pytest.raises(HTTPException):
                await export_map(session, settings, "task", payload, provider)
    assert calls == [1]


def test_external_write_requires_access_code(client, monkeypatch):
    from backend.app import config

    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: Settings(_env_file=None, api_access_code="fake", api_rate_limit_enabled=False),
    )
    result = client.post("/api/v2/tasks/task/personal-map", json={"version": 1, "confirmed": True})
    assert result.status_code == 401
