"""Persistence and worker-policy tests for Phase 2 durable tasks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from backend.app.db.models import SourceEvidenceRecord, TripSourceLink, TripTask, TripVersion
from backend.app.db.repository import create_or_get_task, get_task, save_trip_version
from backend.app.domain.research_models import SourceEvidence
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE
from backend.app.workers import trip_tasks
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker


def _create_task(factory: sessionmaker[Session]) -> str:
    with factory() as session:
        task, _ = create_or_get_task(
            session,
            request_payload=TRIP_REQUEST_V2_EXAMPLE,
            idempotency_key="test-durable-task",
        )
        return task.id


def test_trip_version_insert_is_idempotent(db_session_factory: sessionmaker[Session]) -> None:
    task_id = _create_task(db_session_factory)
    with db_session_factory() as session:
        task = get_task(session, task_id)
        assert task is not None
        first = save_trip_version(
            session, trip_id=task.trip_id, version=1, payload={"success": True}
        )
        second = save_trip_version(
            session, trip_id=task.trip_id, version=1, payload={"success": True}
        )
        count = session.scalar(select(func.count()).select_from(TripVersion))

    assert first.id == second.id
    assert count == 1


def test_trip_version_persists_source_evidence_and_idempotent_links(
    db_session_factory: sessionmaker[Session],
) -> None:
    task_id = _create_task(db_session_factory)
    evidence = SourceEvidence(
        id="b3896f49-e6f8-505f-b748-25a8ac89bca1",
        title="Official notice",
        url="https://tourism.example/notice",
        domain="tourism.example",
        provider="test",
        claim_type="closure",
        claim_text="Open during the requested dates.",
        fetched_at=datetime(2026, 8, 8, 10, tzinfo=timezone.utc),
        freshness_status="unknown",
        trust_level="official",
        confidence=0.9,
    )
    with db_session_factory() as session:
        task = get_task(session, task_id)
        assert task is not None
        first = save_trip_version(
            session,
            trip_id=task.trip_id,
            version=1,
            payload={"success": True},
            source_evidence=[evidence],
        )
        second = save_trip_version(
            session,
            trip_id=task.trip_id,
            version=1,
            payload={"success": True},
            source_evidence=[evidence],
        )
        source_count = session.scalar(select(func.count()).select_from(SourceEvidenceRecord))
        link_count = session.scalar(select(func.count()).select_from(TripSourceLink))

    assert first.id == second.id
    assert source_count == 1
    assert link_count == 1


def test_unknown_source_deduplicates_across_fetch_buckets(
    db_session_factory: sessionmaker[Session],
) -> None:
    task_id = _create_task(db_session_factory)
    base = {
        "id": "7f558980-3620-55a9-a33a-28770bd1e907",
        "title": "Source unavailable",
        "provider": "fallback",
        "claim_type": "reservation",
        "claim_text": "No verified source was found.",
        "freshness_status": "unknown",
        "trust_level": "unknown",
        "confidence": 0,
    }
    first = SourceEvidence(
        **base,
        fetched_at=datetime(2026, 8, 8, 10, tzinfo=timezone.utc),
    )
    second = SourceEvidence(
        **base,
        fetched_at=datetime(2026, 8, 8, 12, tzinfo=timezone.utc),
    )

    with db_session_factory() as session:
        task = get_task(session, task_id)
        assert task is not None
        save_trip_version(
            session,
            trip_id=task.trip_id,
            version=1,
            payload={"success": True},
            source_evidence=[first],
        )
        save_trip_version(
            session,
            trip_id=task.trip_id,
            version=1,
            payload={"success": True},
            source_evidence=[second],
        )
        source_count = session.scalar(select(func.count()).select_from(SourceEvidenceRecord))
        link_count = session.scalar(select(func.count()).select_from(TripSourceLink))

    assert source_count == 1
    assert link_count == 1


def test_new_session_reads_running_task_after_api_session_closes(
    db_session_factory: sessionmaker[Session],
) -> None:
    task_id = _create_task(db_session_factory)
    with db_session_factory() as first_session:
        task = get_task(first_session, task_id, for_update=True)
        assert task is not None
        task.status = "processing"
        first_session.commit()

    with db_session_factory() as restarted_api_session:
        recovered = get_task(restarted_api_session, task_id)
        assert recovered is not None
        assert recovered.status == "processing"


def test_worker_invokes_legacy_adapter_and_persists_one_version(
    db_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id = _create_task(db_session_factory)
    calls: list[str] = []

    async def fake_planner(task_id_arg, payload, progress_callback):
        calls.append(task_id_arg)
        await progress_callback("planning", "Synthetic planner progress.", 50)
        return {"success": True, "plan_id": task_id_arg, "data": {"city": "Tokyo"}}

    class FakeLock:
        def extend(self, *_args, **_kwargs):
            return True

    class FakeTask:
        def retry(self, **_kwargs):
            raise AssertionError("Successful planner must not retry.")

    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(trip_tasks, "_run_legacy_planner", fake_planner)
    monkeypatch.setattr(trip_tasks, "publish_task_event", lambda *_args, **_kwargs: None)

    result = trip_tasks._execute_task(FakeTask(), task_id, FakeLock(), 60)

    with db_session_factory() as session:
        task = get_task(session, task_id)
        version_count = session.scalar(select(func.count()).select_from(TripVersion))
    assert result["status"] == "completed"
    assert task is not None and task.status == "completed"
    assert calls == [task_id]
    assert version_count == 1


def test_worker_startup_recovers_stale_processing_task(
    db_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id = _create_task(db_session_factory)
    with db_session_factory() as session:
        task = get_task(session, task_id, for_update=True)
        assert task is not None
        task.status = "processing"
        task.attempt_count = 1
        task.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        task.celery_task_id = "lost-worker-message"
        session.commit()

    dispatched: list[str] = []
    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(trip_tasks, "_execution_lock_active", lambda _task_id: False)
    monkeypatch.setattr(
        trip_tasks,
        "enqueue_trip_task",
        lambda recovered_task_id: dispatched.append(recovered_task_id) or "recovered-message",
    )
    monkeypatch.setattr(trip_tasks, "publish_task_event", lambda *_args, **_kwargs: None)

    summary = trip_tasks.recover_incomplete_tasks(stale_after_seconds=60)

    with db_session_factory() as session:
        recovered = get_task(session, task_id)
    assert summary == {"dispatched": 1, "failed": 0, "cancelled": 0}
    assert dispatched == [task_id]
    assert recovered is not None and recovered.status == "retrying"
    assert recovered.celery_task_id == "recovered-message"


def test_worker_startup_explicitly_fails_exhausted_task(
    db_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id = _create_task(db_session_factory)
    with db_session_factory() as session:
        task = session.get(TripTask, task_id)
        assert task is not None
        task.status = "processing"
        task.attempt_count = task.max_attempts
        task.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        session.commit()

    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(trip_tasks, "_execution_lock_active", lambda _task_id: False)
    monkeypatch.setattr(trip_tasks, "publish_task_event", lambda *_args, **_kwargs: None)

    summary = trip_tasks.recover_incomplete_tasks(stale_after_seconds=60)

    with db_session_factory() as session:
        failed = get_task(session, task_id)
    assert summary == {"dispatched": 0, "failed": 1, "cancelled": 0}
    assert failed is not None and failed.status == "failed"
    assert failed.error_code == "worker_lost"


def test_worker_startup_finishes_interrupted_cancellation(
    db_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id = _create_task(db_session_factory)
    with db_session_factory() as session:
        task = session.get(TripTask, task_id)
        assert task is not None
        task.status = "cancel_requested"
        task.cancel_requested = True
        session.commit()

    dispatched: list[str] = []
    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(
        trip_tasks,
        "enqueue_trip_task",
        lambda recovered_task_id: dispatched.append(recovered_task_id) or "unexpected-message",
    )
    monkeypatch.setattr(trip_tasks, "publish_task_event", lambda *_args, **_kwargs: None)

    summary = trip_tasks.recover_incomplete_tasks(stale_after_seconds=60)

    with db_session_factory() as session:
        cancelled = get_task(session, task_id)
    assert summary == {"dispatched": 0, "failed": 0, "cancelled": 1}
    assert dispatched == []
    assert cancelled is not None and cancelled.status == "cancelled"
    assert cancelled.finished_at is not None


def test_worker_periodic_recovery_redelivers_stale_queued_broker_message(
    db_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id = _create_task(db_session_factory)
    with db_session_factory() as session:
        task = get_task(session, task_id, for_update=True)
        assert task is not None
        task.celery_task_id = "lost-broker-message"
        task.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        session.commit()

    dispatched: list[str] = []

    def enqueue_replacement(recovered_task_id: str) -> str:
        with db_session_factory() as session:
            claimed = get_task(session, recovered_task_id)
            assert claimed is not None
            assert claimed.celery_task_id is not None
            assert claimed.celery_task_id.startswith("recovery-")
        dispatched.append(recovered_task_id)
        return "replacement-message"

    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(
        trip_tasks,
        "enqueue_trip_task",
        enqueue_replacement,
    )
    monkeypatch.setattr(trip_tasks, "publish_task_event", lambda *_args, **_kwargs: None)

    summary = trip_tasks.recover_incomplete_tasks(stale_after_seconds=60)

    with db_session_factory() as session:
        recovered = get_task(session, task_id)
    assert summary == {"dispatched": 1, "failed": 0, "cancelled": 0}
    assert dispatched == [task_id]
    assert recovered is not None and recovered.celery_task_id == "replacement-message"


def test_worker_recovery_skips_fresh_queued_broker_message(
    db_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id = _create_task(db_session_factory)
    with db_session_factory() as session:
        task = get_task(session, task_id, for_update=True)
        assert task is not None
        task.celery_task_id = "live-broker-message"
        session.commit()

    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(
        trip_tasks,
        "enqueue_trip_task",
        lambda _task_id: pytest.fail("Fresh broker message must not be redelivered."),
    )

    summary = trip_tasks.recover_incomplete_tasks(stale_after_seconds=60)

    assert summary == {"dispatched": 0, "failed": 0, "cancelled": 0}


def test_worker_recovery_skips_processing_task_with_live_lock(
    db_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id = _create_task(db_session_factory)
    with db_session_factory() as session:
        task = get_task(session, task_id, for_update=True)
        assert task is not None
        task.status = "processing"
        task.attempt_count = 1
        task.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        session.commit()

    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(trip_tasks, "_execution_lock_active", lambda _task_id: True)
    monkeypatch.setattr(
        trip_tasks,
        "enqueue_trip_task",
        lambda _task_id: pytest.fail("Live execution must not be redelivered."),
    )

    summary = trip_tasks.recover_incomplete_tasks(stale_after_seconds=60)

    with db_session_factory() as session:
        task = get_task(session, task_id)
    assert summary == {"dispatched": 0, "failed": 0, "cancelled": 0}
    assert task is not None and task.status == "processing"


def test_worker_creates_cross_thread_renewable_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    lock_arguments: dict[str, object] = {}

    class FakeLock:
        def acquire(self, **_kwargs):
            return True

        def release(self):
            return True

    class FakeRedisClient:
        def lock(self, _name, **kwargs):
            lock_arguments.update(kwargs)
            return FakeLock()

        def close(self):
            return None

    monkeypatch.setattr(
        trip_tasks.Redis,
        "from_url",
        lambda *_args, **_kwargs: FakeRedisClient(),
    )
    monkeypatch.setattr(
        trip_tasks,
        "_execute_task",
        lambda _self, task_id, _lock, _timeout: {"task_id": task_id, "status": "completed"},
    )

    result = trip_tasks.run_trip_planning.run("task_lock_test")

    assert result["status"] == "completed"
    assert lock_arguments["thread_local"] is False
