"""Phase 7 trace, telemetry, and runtime manifest tests."""

from __future__ import annotations

from backend.app.db.repository import (
    create_or_get_task,
    list_task_telemetry,
    record_telemetry_event,
    save_trip_version,
)
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE
from backend.app.workers.trip_tasks import PlannerExecution, _persist_execution_telemetry
from sqlalchemy.orm import Session, sessionmaker


def test_trace_header_propagates_into_durable_task(client) -> None:
    trace_id = "trace_external_12345678"

    response = client.post(
        "/api/v2/trips",
        json=TRIP_REQUEST_V2_EXAMPLE,
        headers={"X-Trace-ID": trace_id},
    )

    assert response.status_code == 202
    assert response.headers["X-Trace-ID"] == trace_id
    assert response.json()["trace_id"] == trace_id


def test_telemetry_endpoint_redacts_sensitive_metadata(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    created = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE).json()
    with db_session_factory() as session:
        record_telemetry_event(
            session,
            trace_id=created["trace_id"],
            task_id=created["task_id"],
            trip_id=created["trip_id"],
            component="tool",
            operation="provider_call",
            status="failed",
            node="research",
            tool="web_search",
            latency_ms=123,
            cache_hit=False,
            metadata={
                "error_code": "rate_limited",
                "api_key": "must-not-leak",
                "nested": {"cookie": "must-not-leak"},
            },
        )

    response = client.get(f"/api/v2/trips/tasks/{created['task_id']}/telemetry")

    assert response.status_code == 200
    event = response.json()[0]
    assert event["trace_id"] == created["trace_id"]
    assert event["node"] == "research"
    assert event["tool"] == "web_search"
    assert event["metadata"]["api_key"] == "[REDACTED]"
    assert event["metadata"]["nested"]["cookie"] == "[REDACTED]"
    assert "must-not-leak" not in response.text


def test_trip_version_persists_runtime_manifest(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    created = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE).json()
    with db_session_factory() as session:
        version = save_trip_version(
            session,
            trip_id=created["trip_id"],
            version=1,
            payload={"success": True},
            planner_engine="journey_graph",
            schema_version="2.0",
            model_id="test-model",
            prompt_version="prompt/1",
            workflow_version="workflow/1",
            tool_versions={"web_research": "2.0"},
            usage_summary={"total_tokens": 321, "model_cost_usd": 0.0123},
            activate=True,
        )

    response = client.get(f"/api/v2/trips/{created['trip_id']}/versions/{version.version}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_id"] == "test-model"
    assert payload["prompt_version"] == "prompt/1"
    assert payload["workflow_version"] == "workflow/1"
    assert payload["tool_versions"] == {"web_research": "2.0"}
    assert payload["usage_summary"]["total_tokens"] == 321


def test_resume_telemetry_does_not_double_count_generation_tokens(
    db_session_factory: sessionmaker[Session],
) -> None:
    generation = {
        "model_generation": {
            "status": "success",
            "input_tokens": 40,
            "output_tokens": 60,
            "total_tokens": 100,
            "model_cost_usd": 0.01,
        }
    }
    with db_session_factory() as session:
        task, _ = create_or_get_task(
            session,
            request_payload=TRIP_REQUEST_V2_EXAMPLE,
            idempotency_key="telemetry-resume-test",
        )
        common = {
            "engine": "journey_graph",
            "client_payload": {"success": True},
            "schema_version": "2.0",
            "model_id": "test-model",
            "prompt_version": "prompt/1",
            "workflow_version": "workflow/1",
        }
        _persist_execution_telemetry(
            session,
            trace_id=task.trace_id,
            task_id=task.id,
            trip_id=task.trip_id,
            execution=PlannerExecution(**common, metrics={**generation, "model_invoked": True}),
        )
        _persist_execution_telemetry(
            session,
            trace_id=task.trace_id,
            task_id=task.id,
            trip_id=task.trip_id,
            execution=PlannerExecution(**common, metrics={**generation, "model_invoked": False}),
        )
        events = list_task_telemetry(session, task.id)

    assert [event.operation for event in events] == ["engine_run", "engine_resume"]
    assert sum(event.total_tokens for event in events) == 100
    assert sum(event.model_cost_usd for event in events) == 0.01
