"""Real PostgreSQL and Redis checks enabled by CI or an integration environment."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from backend.app.agents.journey_graph import build_journey_graph
from backend.app.agents.journey_graph.checkpoint import open_postgres_checkpointer
from backend.app.db.repository import create_or_get_task, get_task, save_trip_version
from backend.app.db.session import build_engine
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE
from backend.app.services.task_events import publish_task_event, task_channel
from langgraph.types import Command
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
REDIS_URL = os.getenv("TEST_REDIS_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not REDIS_URL,
    reason="TEST_DATABASE_URL and TEST_REDIS_URL are required for integration checks.",
)


def test_independent_api_sessions_share_task_and_deduplicate_version() -> None:
    key = f"integration-{uuid4()}"
    first_engine = build_engine(DATABASE_URL)
    first_factory = sessionmaker(bind=first_engine, expire_on_commit=False)
    with first_factory() as session:
        task, created = create_or_get_task(
            session,
            request_payload=TRIP_REQUEST_V2_EXAMPLE,
            idempotency_key=key,
        )
        assert created is True
        task_id = task.id
        trip_id = task.trip_id
    first_engine.dispose()

    second_engine = build_engine(DATABASE_URL)
    second_factory = sessionmaker(bind=second_engine, expire_on_commit=False)
    with second_factory() as session:
        recovered = get_task(session, task_id)
        assert recovered is not None
        first_version = save_trip_version(
            session, trip_id=trip_id, version=1, payload={"source": "integration"}
        )
        second_version = save_trip_version(
            session, trip_id=trip_id, version=1, payload={"source": "integration"}
        )
        version_count = session.scalar(
            select(func.count()).where(first_version.__class__.trip_id == trip_id)
        )
        session.delete(recovered.trip)
        session.commit()
    second_engine.dispose()

    assert first_version.id == second_version.id
    assert version_count == 1


def test_task_event_round_trip_uses_redis_pubsub() -> None:
    key = f"redis-integration-{uuid4()}"
    engine = build_engine(DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    with factory() as session:
        task, _ = create_or_get_task(
            session,
            request_payload=TRIP_REQUEST_V2_EXAMPLE,
            idempotency_key=key,
        )
        channel = task_channel(task.id)
        pubsub = client.pubsub()
        pubsub.subscribe(channel)
        pubsub.get_message(timeout=1)
        publish_task_event(task, client=client)
        event = pubsub.get_message(ignore_subscribe_messages=True, timeout=2)
        session.delete(task.trip)
        session.commit()

    pubsub.close()
    client.close()
    engine.dispose()

    assert event is not None
    assert task.id in event["data"]


def test_postgres_checkpoint_resumes_with_a_new_connection() -> None:
    thread_id = f"checkpoint-integration-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "trip_id": f"trip_{uuid4().hex}",
        "task_id": f"task_{uuid4().hex}",
        "request": TRIP_REQUEST_V2_EXAMPLE,
    }

    with open_postgres_checkpointer(DATABASE_URL, setup=True) as first_saver:
        interrupted_graph = build_journey_graph(
            checkpointer=first_saver,
            interrupt_before=["persist"],
        )
        interrupted = interrupted_graph.invoke(initial_state, config)
        snapshot = interrupted_graph.get_state(config)
        assert "final_plan" not in interrupted
        assert snapshot.next == ("persist",)

    with open_postgres_checkpointer(DATABASE_URL) as second_saver:
        resumed_graph = build_journey_graph(checkpointer=second_saver)
        completed = resumed_graph.invoke(None, config)
        snapshot = resumed_graph.get_state(config)
        assert completed["final_plan"].schema_version == "2.0"
        assert snapshot.next == ()
        second_saver.delete_thread(thread_id)


def test_human_review_interrupt_resumes_after_checkpointer_reconnect() -> None:
    thread_id = f"human-review-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "trip_id": f"trip_{uuid4().hex}",
        "task_id": f"task_{uuid4().hex}",
        "request": TRIP_REQUEST_V2_EXAMPLE,
    }

    with open_postgres_checkpointer(DATABASE_URL, setup=True) as first_saver:
        graph = build_journey_graph(
            checkpointer=first_saver,
            require_human_review=True,
        )
        proposal = graph.invoke(initial_state, config)
        snapshot = graph.get_state(config)
        assert snapshot.next == ("human_review",)
        assert proposal["draft_plan"].schema_version == "2.0"

    with open_postgres_checkpointer(DATABASE_URL) as second_saver:
        resumed = build_journey_graph(
            checkpointer=second_saver,
            require_human_review=True,
        )
        completed = resumed.invoke(Command(resume={"action": "approve"}), config)
        assert resumed.get_state(config).next == ()
        assert completed["approval_status"] == "approved"
        assert completed["final_plan"].schema_version == "2.0"
        second_saver.delete_thread(thread_id)
