"""Contract tests for durable v2 trip task endpoints."""

from __future__ import annotations

import sys
from typing import Any

from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE


def _payload_with(**overrides: Any) -> dict[str, Any]:
    payload = dict(TRIP_REQUEST_V2_EXAMPLE)
    payload.update(overrides)
    return payload


def test_v2_create_trip_persists_before_dispatch_without_importing_planner(client) -> None:
    planner_module = "backend.app.agents.trip_planner_agent"
    sys.modules.pop(planner_module, None)

    response = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE)

    body = response.json()
    assert response.status_code == 202
    assert body["status"] == "queued"
    assert body["task_id"].startswith("task_")
    assert body["trip_id"].startswith("trip_")
    assert body["message"] == "Task queued for durable execution."
    assert planner_module not in sys.modules

    persisted = client.get(f"/api/v2/trips/tasks/{body['task_id']}")
    assert persisted.status_code == 200
    assert persisted.json() == body


def test_v2_canonical_trip_and_task_resource_paths(client) -> None:
    created = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE).json()

    trip = client.get(f"/api/v2/trips/{created['trip_id']}")
    task = client.get(f"/api/v2/tasks/{created['task_id']}")
    events = client.get(f"/api/v2/tasks/{created['task_id']}/events")

    assert trip.status_code == 200
    assert trip.json()["request"]["origin"] == TRIP_REQUEST_V2_EXAMPLE["origin"]
    assert trip.json()["task"] == created
    assert task.status_code == 200
    assert task.json() == created
    assert events.status_code == 200
    assert events.json() == []


def test_v2_trip_feedback_is_persisted_without_dispatch(
    client,
    db_session_factory,
) -> None:
    from backend.app.db.models import UserFeedback
    from sqlalchemy import select

    created = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE).json()
    response = client.post(
        f"/api/v2/trips/{created['trip_id']}/feedback",
        json={
            "rating": 4,
            "category": "plan_quality",
            "comment": "The route order was useful.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["feedback_id"].startswith("feedback_")
    assert body["trip_id"] == created["trip_id"]
    assert body["task_id"] == created["task_id"]
    assert body["rating"] == 4
    assert body["category"] == "plan_quality"
    with db_session_factory() as session:
        record = session.scalar(select(UserFeedback))
        assert record is not None
        assert record.comment == "The route order was useful."


def test_v2_trip_feedback_rejects_empty_or_unknown_resources(client) -> None:
    created = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE).json()

    empty = client.post(
        f"/api/v2/trips/{created['trip_id']}/feedback",
        json={},
    )
    missing_trip = client.post(
        "/api/v2/trips/trip_missing/feedback",
        json={"rating": 5},
    )
    missing_version = client.post(
        f"/api/v2/trips/{created['trip_id']}/feedback",
        json={"rating": 5, "version": 99},
    )

    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "validation_error"
    assert missing_trip.status_code == 404
    assert missing_trip.json()["error"]["code"] == "not_found"
    assert missing_version.status_code == 404
    assert missing_version.json()["error"]["code"] == "not_found"


def test_v2_duplicate_payload_returns_same_durable_task(client) -> None:
    first = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE)
    second = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["task_id"] == first.json()["task_id"]
    assert second.json()["trip_id"] == first.json()["trip_id"]


def test_v2_idempotency_header_controls_deduplication(client) -> None:
    first = client.post(
        "/api/v2/trips",
        json=TRIP_REQUEST_V2_EXAMPLE,
        headers={"Idempotency-Key": "mobile-request-1"},
    )
    second = client.post(
        "/api/v2/trips",
        json=TRIP_REQUEST_V2_EXAMPLE,
        headers={"Idempotency-Key": "mobile-request-2"},
    )

    assert first.json()["task_id"] != second.json()["task_id"]


def test_v2_reused_idempotency_key_rejects_different_payload(client) -> None:
    first = client.post(
        "/api/v2/trips",
        json=TRIP_REQUEST_V2_EXAMPLE,
        headers={"Idempotency-Key": "mobile-request-conflict"},
    )
    conflicting = client.post(
        "/api/v2/trips",
        json=_payload_with(origin="Beijing"),
        headers={"Idempotency-Key": "mobile-request-conflict"},
    )

    assert first.status_code == 202
    assert conflicting.status_code == 409
    assert conflicting.json()["error"]["code"] == "conflict"


def test_v2_dispatch_confirmation_failure_stays_recoverable(
    client,
    db_session_factory,
    monkeypatch,
) -> None:
    from backend.app.api.v2 import trips as v2_trip_routes
    from backend.app.db.models import TripTask
    from sqlalchemy import select

    def fail_confirmation(*_args, **_kwargs):
        raise RuntimeError("synthetic confirmation failure")

    monkeypatch.setattr(v2_trip_routes, "attach_celery_task", fail_confirmation)
    response = client.post(
        "/api/v2/trips",
        json=TRIP_REQUEST_V2_EXAMPLE,
        headers={"Idempotency-Key": "dispatch-confirmation-failure"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    with db_session_factory() as session:
        task = session.scalar(select(TripTask))
        assert task is not None
        assert task.status == "queued"
        assert task.celery_task_id is None


def test_v2_cancel_and_retry_queued_task(client) -> None:
    created = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE).json()

    cancelled = client.post(f"/api/v2/trips/tasks/{created['task_id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    retried = client.post(f"/api/v2/trips/tasks/{created['task_id']}/retry")
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    assert retried.json()["attempt_count"] == 0


def test_v2_missing_task_returns_v2_error(client) -> None:
    response = client.get("/api/v2/trips/tasks/task_missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_v2_invalid_date_returns_v2_error_envelope(client) -> None:
    response = client.post("/api/v2/trips", json=_payload_with(start_date="2026-02-30"))

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed."
    assert body["error"]["details"][0]["field"] == "start_date"


def test_v2_reversed_dates_return_v2_error_envelope(client) -> None:
    response = client.post(
        "/api/v2/trips",
        json=_payload_with(start_date="2026-10-14", end_date="2026-10-10"),
    )

    body = response.json()
    assert response.status_code == 422
    assert any(
        detail["message"] == "Value error, end_date must be on or after start_date"
        for detail in body["error"]["details"]
    )


def test_v2_out_of_range_days_return_v2_error_envelope(client) -> None:
    response = client.post("/api/v2/trips", json=_payload_with(travel_days=31))

    assert response.status_code == 422
    assert any(detail["field"] == "travel_days" for detail in response.json()["error"]["details"])


def test_v2_inconsistent_days_return_v2_error_envelope(client) -> None:
    response = client.post("/api/v2/trips", json=_payload_with(travel_days=4))

    assert response.status_code == 422
    assert any(
        detail["message"] == "Value error, travel_days must match the inclusive date range"
        for detail in response.json()["error"]["details"]
    )


def test_v2_non_positive_budget_returns_v2_error_envelope(client) -> None:
    response = client.post("/api/v2/trips", json=_payload_with(budget_total=0))

    assert response.status_code == 422
    assert any(detail["field"] == "budget_total" for detail in response.json()["error"]["details"])


def test_v2_unhandled_exception_returns_error_envelope(client) -> None:
    response = client.get("/api/v2/_test/unhandled")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_server_error"


def test_unknown_v2_route_returns_error_envelope(client) -> None:
    response = client.get("/api/v2/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_v2_error_prefix_does_not_capture_future_api_versions(client) -> None:
    response = client.get("/api/v20/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_openapi_includes_durable_v2_examples(client) -> None:
    schema = client.get("/openapi.json").json()
    post_operation = schema["paths"]["/api/v2/trips"]["post"]

    request_examples = post_operation["requestBody"]["content"]["application/json"]["examples"]
    accepted_example = post_operation["responses"]["202"]["content"]["application/json"]["example"]
    conflict_example = post_operation["responses"]["409"]["content"]["application/json"]["example"]

    assert "durable_submission" in request_examples
    assert accepted_example["status"] == "queued"
    assert conflict_example["error"]["code"] == "conflict"
    for path in (
        "/api/v2/trips/{trip_id}",
        "/api/v2/trips/{trip_id}/approve",
        "/api/v2/trips/{trip_id}/replan",
        "/api/v2/trips/{trip_id}/feedback",
        "/api/v2/tasks/{task_id}",
        "/api/v2/tasks/{task_id}/events",
    ):
        assert path in schema["paths"]
