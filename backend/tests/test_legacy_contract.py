"""Contract tests that freeze existing legacy response shapes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.app.db.models import Trip, TripTask
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "legacy"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def test_completed_task_status_matches_legacy_fixture(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    expected = _load_fixture("trip_status_completed.json")
    with db_session_factory() as session:
        trip = Trip(
            id="trip-legacy-fixture",
            idempotency_key="legacy-fixture",
            request_payload={"contract": "legacy", "request": {"city": "西安"}},
        )
        session.add(
            TripTask(
                id=expected["task_id"],
                trip=trip,
                status="completed",
                stage="completed",
                progress=100,
                message="旅行计划生成成功",
                result_payload=expected["result"],
            )
        )
        session.commit()

    response = client.get(f"/api/trip/status/{expected['task_id']}")

    assert response.status_code == 200
    assert response.json() == expected


def test_missing_task_status_preserves_legacy_404_shape(client) -> None:
    expected = _load_fixture("trip_status_not_found.json")

    response = client.get("/api/trip/status/missing-task")

    assert response.status_code == 404
    assert response.json() == expected


def test_legacy_submission_uses_durable_store_without_loading_planner(
    client,
    db_session_factory: sessionmaker[Session],
    tasks_dir: Path,
) -> None:
    planner_module = "backend.app.agents.trip_planner_agent"
    sys.modules.pop(planner_module, None)
    payload = {
        "city": "Tokyo",
        "cities": [{"city": "Tokyo", "days": 2}],
        "start_date": "2026-10-10",
        "end_date": "2026-10-11",
        "travel_days": 2,
        "transportation": "public transit",
        "accommodation": "midscale hotel",
        "preferences": ["food"],
        "free_text_input": "",
        "language": "en",
    }

    response = client.post(
        "/api/trip/plan",
        json=payload,
        headers={"Idempotency-Key": "legacy-mobile-request"},
    )
    repeated = client.post(
        "/api/trip/plan",
        json=payload,
        headers={"Idempotency-Key": "legacy-mobile-request"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    assert repeated.json()["task_id"] == response.json()["task_id"]
    assert planner_module not in sys.modules
    assert list(tasks_dir.glob("*.json")) == []
    with db_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(TripTask)) == 1


def test_legacy_reused_idempotency_key_rejects_different_payload(client) -> None:
    payload = {
        "city": "Tokyo",
        "cities": [{"city": "Tokyo", "days": 2}],
        "start_date": "2026-10-10",
        "end_date": "2026-10-11",
        "travel_days": 2,
        "transportation": "public transit",
        "accommodation": "midscale hotel",
        "preferences": ["food"],
        "free_text_input": "",
        "language": "en",
    }
    conflicting = {
        **payload,
        "city": "Kyoto",
        "cities": [{"city": "Kyoto", "days": 2}],
    }

    first = client.post(
        "/api/trip/plan",
        json=payload,
        headers={"Idempotency-Key": "legacy-conflict"},
    )
    second = client.post(
        "/api/trip/plan",
        json=conflicting,
        headers={"Idempotency-Key": "legacy-conflict"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json() == {"detail": "幂等键已用于不同的请求内容"}


def test_original_planner_import_path_remains_compatible() -> None:
    from backend.app.agents import trip_planner_agent as compatibility_module
    from backend.app.agents.legacy import trip_planner_agent as legacy_module

    assert compatibility_module.MultiAgentTripPlanner is legacy_module.MultiAgentTripPlanner
    assert compatibility_module.get_trip_planner_agent is legacy_module.get_trip_planner_agent
    assert compatibility_module.reset_trip_planner_agent is legacy_module.reset_trip_planner_agent
