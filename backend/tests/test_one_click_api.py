"""Input pauses, access checks and immutable quote proposals without external calls."""

from backend.app.api.v2 import trips
from backend.app.db.models import TripTask
from backend.app.db.repository import save_trip_version
from backend.app.services import guardrails
from backend.tests.test_one_click_travel import request, settings


def configure(monkeypatch):
    config = settings().model_copy(
        update={"api_rate_limit_enabled": False, "api_access_code_required": False}
    )
    monkeypatch.setattr(trips, "get_settings", lambda: config)
    monkeypatch.setattr(guardrails, "get_settings", lambda: config)
    return config


def test_pause_restore_continue_and_duplicate_submit(client, db_session_factory, monkeypatch):
    configure(monkeypatch)
    payload = request().model_dump(mode="json")
    first = client.post("/api/v2/trips", json=payload)
    assert first.status_code == 202, first.text
    record = first.json()
    duplicate = client.post("/api/v2/trips", json=payload).json()
    assert duplicate["task_id"] == record["task_id"]
    task_id = record["task_id"]
    with db_session_factory() as session:
        task = session.get(TripTask, task_id)
        task.status = "awaiting_input"
        task.pending_input = {"code": "no_hotel", "message": "调整住宿", "provider": "hotel"}
        session.commit()
    assert (
        client.get(f"/api/v2/trips/tasks/{task_id}").json()["pending_input"]["provider"] == "hotel"
    )
    assert client.get(f"/api/v2/trips/{record['trip_id']}").json()["request"]["origin"] == "上海"
    continued = client.post(
        f"/api/v2/trips/tasks/{task_id}/continue", json={"request": payload, "refresh": "hotel"}
    )
    assert continued.status_code == 202, continued.text
    assert continued.json()["pending_input"] is None
    assert (
        client.post(
            f"/api/v2/trips/tasks/{task_id}/continue", json={"request": payload}
        ).status_code
        == 409
    )
    with db_session_factory() as session:
        assert session.get(TripTask, task_id).trip.request_payload["quote_revision"] == {"hotel": 1}


def test_continue_is_access_protected(client, db_session_factory, monkeypatch):
    config = configure(monkeypatch)
    payload = request().model_dump(mode="json")
    record = client.post("/api/v2/trips", json=payload).json()
    with db_session_factory() as session:
        task = session.get(TripTask, record["task_id"])
        task.status = "awaiting_input"
        session.commit()
    config.api_access_code_required = True
    from pydantic import SecretStr

    config.api_access_code = SecretStr("test-only-access")
    assert (
        client.post(
            f"/api/v2/trips/tasks/{record['task_id']}/continue", json={"request": payload}
        ).status_code
        == 401
    )


def test_continue_legacy_model_failure_changes_only_model_revision(
    client, db_session_factory, monkeypatch
):
    configure(monkeypatch)
    payload = request(quote_revision={"hotel": 2}).model_dump(mode="json")
    record = client.post("/api/v2/trips", json=payload).json()
    task_id = record["task_id"]
    with db_session_factory() as session:
        task = session.get(TripTask, task_id)
        task.status = "awaiting_input"
        task.pending_input = {"code": "model_output", "provider": None}
        session.commit()
    endpoint = f"/api/v2/trips/tasks/{task_id}/continue"
    assert client.post(endpoint, json={"request": payload}).status_code == 202
    assert client.post(endpoint, json={"request": payload}).status_code == 409
    with db_session_factory() as session:
        persisted = session.get(TripTask, task_id).trip.request_payload
        assert persisted["quote_revision"] == {"hotel": 2, "model": 1}
        assert request(quote_revision=persisted["quote_revision"]).quote_revision["model"] == 1


def test_version_and_confirmed_request_saved_together(client, db_session_factory, monkeypatch):
    configure(monkeypatch)
    payload = request().model_dump(mode="json")
    record = client.post("/api/v2/trips", json=payload).json()
    revised = {**payload, "hotel_tier": "premium"}
    native = {"travel_summary": {"planning_request": revised, "hotel": {"cost_cents": 140000}}}
    with db_session_factory() as session:
        version = save_trip_version(
            session,
            trip_id=record["trip_id"],
            version=1,
            payload={},
            native_payload=native,
            activate=True,
        )
        assert session.get(TripTask, record["task_id"]).trip.request_payload == revised
        again = save_trip_version(
            session,
            trip_id=record["trip_id"],
            version=1,
            payload={},
            native_payload={"different": True},
            activate=True,
        )
        assert again.id == version.id
        assert again.native_payload == native


def test_worker_input_pause_is_durable_not_retried(client, db_session_factory, monkeypatch):
    from backend.app.services.travel_ledger import PlanningInputRequired
    from backend.app.workers import trip_tasks

    configure(monkeypatch)
    record = client.post("/api/v2/trips", json=request().model_dump(mode="json")).json()
    calls = []

    async def pause(*args, **kwargs):
        calls.append(1)
        raise PlanningInputRequired("no_hotel", "请调整住宿", provider="hotel")

    class Lock:
        def extend(self, *args, **kwargs):
            return True

    class Worker:
        def retry(self, **kwargs):
            raise AssertionError("input pauses must never auto-retry suppliers")

    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(trip_tasks, "_run_configured_planners", pause)
    monkeypatch.setattr(trip_tasks, "publish_task_event", lambda *args, **kwargs: None)
    first = trip_tasks._execute_task(Worker(), record["task_id"], Lock(), 60)
    assert first["status"] == "awaiting_input"
    again = trip_tasks._execute_task(Worker(), record["task_id"], Lock(), 60)
    assert again["status"] == "awaiting_input"
    assert calls == [1]
    assert (
        client.get(f"/api/v2/trips/tasks/{record['task_id']}").json()["pending_input"]["code"]
        == "no_hotel"
    )


def test_resuming_failed_validation_cannot_skip_to_approval(monkeypatch):
    import asyncio
    from contextlib import contextmanager

    import pytest
    from backend.app.agents.journey_graph import checkpoint
    from backend.app.services.travel_ledger import PlanningInputRequired
    from backend.app.workers import trip_tasks
    from backend.tests.test_one_click_travel import planner
    from langgraph.checkpoint.memory import InMemorySaver

    config = configure(monkeypatch)
    monkeypatch.setattr(trip_tasks, "get_settings", lambda: config)
    memory = InMemorySaver()

    @contextmanager
    def checkpointer():
        yield memory

    monkeypatch.setattr(checkpoint, "open_postgres_checkpointer", checkpointer)
    invalid = planner().run()
    invalid.days[1].timeline[0].end = invalid.days[1].timeline[1].end

    class BrokenPlanner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            return invalid

    monkeypatch.setattr(trip_tasks, "OneClickPlanner", BrokenPlanner)

    async def progress(*args):
        pass

    for _ in range(2):
        with pytest.raises(PlanningInputRequired, match="校验"):
            asyncio.run(
                trip_tasks._run_journey_graph_planner(
                    "test-task", "test-trip", request().model_dump(mode="json"), progress
                )
            )
