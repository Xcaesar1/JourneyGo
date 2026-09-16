"""Phase 6 human-review, scoped replan, diff, and rollback tests."""

from __future__ import annotations

from dataclasses import replace

from backend.app.agents.journey_graph import build_journey_graph
from backend.app.agents.journey_graph.nodes.enrich import enrich_plan
from backend.app.agents.replan_graph import build_replan_graph
from backend.app.db.models import TripVersion
from backend.app.db.repository import (
    create_or_get_task,
    get_active_trip_version,
    get_task,
    list_trip_versions,
    record_pending_review,
    save_trip_version,
    submit_review_decision,
)
from backend.app.domain.review_models import TripReviewDecisionV2
from backend.app.domain.trip_models import (
    TRIP_REQUEST_V2_EXAMPLE,
    AttractionV2,
    LocationV2,
    TripPlanV2,
    TripRequestV2,
)
from backend.app.workers import trip_tasks
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker


def _request() -> TripRequestV2:
    return TripRequestV2.model_validate(TRIP_REQUEST_V2_EXAMPLE)


def _base_plan() -> TripPlanV2:
    request = _request()
    result = build_journey_graph().invoke(
        {"trip_id": "trip-replan", "task_id": "task-replan", "request": request}
    )
    plan = result["final_plan"]
    days = list(plan.days)
    days[0] = days[0].model_copy(
        update={
            "attractions": [
                AttractionV2(
                    name="Museum A",
                    address="A",
                    location=LocationV2(longitude=139.7, latitude=35.6),
                    description="A",
                )
            ]
        }
    )
    days[1] = days[1].model_copy(
        update={
            "attractions": [
                AttractionV2(
                    name="Park B",
                    address="B",
                    location=LocationV2(longitude=139.71, latitude=35.61),
                    description="B",
                )
            ]
        }
    )
    draft = plan.model_copy(update={"days": days})
    enriched = enrich_plan(
        {
            "request": request,
            "draft_plan": draft,
            "route_estimates": plan.route_matrix,
            "transport_options": plan.transport_options,
        }
    )
    return enriched["draft_plan"]


def _create_task(factory: sessionmaker[Session], key: str) -> str:
    with factory() as session:
        task, _created = create_or_get_task(
            session,
            request_payload=TRIP_REQUEST_V2_EXAMPLE,
            idempotency_key=key,
        )
        return task.id


def test_replan_graph_interrupts_and_preserves_unaffected_days() -> None:
    request = _request()
    base = _base_plan()
    checkpointer = InMemorySaver()
    graph = build_replan_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "scoped-replan"}}

    proposal = graph.invoke(
        {
            "trip_id": "trip-replan",
            "task_id": "task-replan",
            "thread_id": "scoped-replan",
            "request": request,
            "original_plan": base,
            "base_plan": base,
            "change_request": {
                "instruction": "Remove Museum A from the first day only.",
                "day_indices": [0],
                "remove_attractions": ["Museum A"],
            },
            "from_version": 1,
            "proposed_version": 2,
        },
        config,
    )

    assert graph.get_state(config).next == ("human_review",)
    assert proposal["impact_scope"].day_indices == [0]
    assert proposal["diff"].changed_day_indices == [0]
    assert 1 in proposal["diff"].unchanged_day_indices
    assert proposal["draft_plan"].days[1] == base.days[1]

    second = graph.invoke(
        Command(
            resume={
                "action": "modify",
                "reason": "Also remove the park.",
                "changes": {
                    "instruction": "Remove Park B from day two.",
                    "day_indices": [1],
                    "remove_attractions": ["Park B"],
                },
            }
        ),
        config,
    )
    assert graph.get_state(config).next == ("human_review",)
    assert second["diff"].changed_day_indices == [0, 1]

    completed = graph.invoke(Command(resume={"action": "approve"}), config)
    assert graph.get_state(config).next == ()
    assert completed["final_plan"].days[0].attractions == []
    assert completed["final_plan"].days[1].attractions == []


def test_worker_saves_no_version_until_review_is_approved(
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    task_id = _create_task(db_session_factory, "human-review-worker")
    plan = _base_plan()
    pending = trip_tasks.PlannerExecution(
        engine="journey_graph",
        client_payload={"success": True, "data": {"city": plan.city}},
        schema_version="2.0",
        native_payload=plan.model_dump(mode="json"),
        source_evidence=tuple(plan.source_evidence),
        workflow_status="awaiting_approval",
        review_workflow_type="initial",
        review_thread_id=task_id,
        review_proposed_version=1,
        validation_report=plan.validation_report.model_dump(mode="json"),
    )

    async def fake_pending(*_args, **_kwargs):
        return trip_tasks.PlannerRunSet(primary=pending)

    class FakeLock:
        def extend(self, *_args, **_kwargs):
            return True

    class FakeTask:
        def retry(self, **_kwargs):
            raise AssertionError(f"Unexpected retry: {_kwargs}")

    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(trip_tasks, "_run_configured_planners", fake_pending)
    monkeypatch.setattr(trip_tasks, "publish_task_event", lambda *_args, **_kwargs: None)

    waiting = trip_tasks._execute_task(FakeTask(), task_id, FakeLock(), 60)
    with db_session_factory() as session:
        task = get_task(session, task_id)
        version_count = session.scalar(select(func.count()).select_from(TripVersion))
    assert waiting["status"] == "awaiting_approval"
    assert task is not None and task.review_payload["status"] == "pending"
    assert version_count == 0

    with db_session_factory() as session:
        submit_review_decision(
            session,
            task_id=task_id,
            decision=TripReviewDecisionV2(action="approve"),
        )

    approved = replace(pending, workflow_status="completed")

    async def fake_approved(*_args, **_kwargs):
        return trip_tasks.PlannerRunSet(primary=approved)

    monkeypatch.setattr(trip_tasks, "_run_configured_planners", fake_approved)
    completed = trip_tasks._execute_task(FakeTask(), task_id, FakeLock(), 60)
    with db_session_factory() as session:
        task = get_task(session, task_id)
        active = get_active_trip_version(session, task.trip_id)
        versions = list_trip_versions(session, task.trip_id)
    assert completed["status"] == "completed"
    assert active is not None and active.version == 1
    assert [item.version for item in versions] == [1]
    assert task.review_payload["status"] == "applied"


def test_no_change_replan_cannot_be_approved(client, db_session_factory) -> None:
    task_id = _create_task(db_session_factory, "no-change-replan")
    plan = _base_plan()
    with db_session_factory() as session:
        record_pending_review(
            session,
            task_id=task_id,
            workflow_type="replan",
            thread_id=f"{task_id}:replan:no-change",
            preview_payload={"success": True, "data": {"city": plan.city}},
            native_payload=plan.model_dump(mode="json"),
            validation_report={"issues": []},
            diff_payload={
                "summary": "No changes.",
                "changed_day_indices": [],
                "unchanged_day_indices": [day.day_index for day in plan.days],
                "entries": [],
            },
            base_version=1,
            proposed_version=2,
        )

    response = client.post(
        f"/api/v2/trips/tasks/{task_id}/review",
        json={"action": "approve"},
    )

    assert response.status_code == 409
    assert "no changes" in response.json()["error"]["message"].lower()


def test_rejected_replan_preserves_active_version(
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    task_id = _create_task(db_session_factory, "reject-replan-preserves-active")
    plan = _base_plan()
    with db_session_factory() as session:
        task = get_task(session, task_id)
        save_trip_version(
            session,
            trip_id=task.trip_id,
            version=1,
            payload={"success": True, "data": {"city": plan.city}},
            planner_engine="journey_graph",
            version_role="primary",
            schema_version="2.0",
            native_payload=plan.model_dump(mode="json"),
            activate=True,
        )
        task.status = "completed"
        task.result_payload = {"success": True, "data": {"city": plan.city}}
        session.commit()
        record_pending_review(
            session,
            task_id=task_id,
            workflow_type="replan",
            thread_id=f"{task_id}:replan:reject",
            preview_payload=task.result_payload,
            native_payload=plan.model_dump(mode="json"),
            validation_report={"issues": []},
            diff_payload={
                "summary": "One change.",
                "changed_day_indices": [0],
                "unchanged_day_indices": [],
                "entries": [
                    {
                        "path": "/days/0/transportation",
                        "operation": "replace",
                        "before": "train",
                        "after": "walking",
                    }
                ],
            },
            base_version=1,
            proposed_version=2,
        )
        submit_review_decision(
            session,
            task_id=task_id,
            decision=TripReviewDecisionV2(action="reject", reason="Keep V1."),
        )

    rejected = trip_tasks.PlannerExecution(
        engine="journey_graph",
        client_payload={"success": True, "data": {"city": plan.city}},
        schema_version="2.0",
        native_payload=plan.model_dump(mode="json"),
        workflow_status="rejected",
        review_workflow_type="replan",
    )

    async def fake_rejected(*_args, **_kwargs):
        return rejected

    class FakeLock:
        def extend(self, *_args, **_kwargs):
            return True

    class FakeTask:
        def retry(self, **_kwargs):
            raise AssertionError(f"Unexpected retry: {_kwargs}")

    monkeypatch.setattr(trip_tasks, "SessionLocal", db_session_factory)
    monkeypatch.setattr(trip_tasks, "_run_replan_planner", fake_rejected)
    monkeypatch.setattr(trip_tasks, "publish_task_event", lambda *_args, **_kwargs: None)

    result = trip_tasks._execute_task(FakeTask(), task_id, FakeLock(), 60)

    with db_session_factory() as session:
        task = get_task(session, task_id)
        versions = list_trip_versions(session, task.trip_id)
    assert result["status"] == "completed"
    assert task.review_payload["status"] == "rejected"
    assert [(version.version, version.version_role) for version in versions] == [(1, "primary")]


def test_review_and_version_endpoints_compare_and_rollback(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    created = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE).json()
    plan = _base_plan()
    with db_session_factory() as session:
        task = get_task(session, created["task_id"])
        record_pending_review(
            session,
            task_id=task.id,
            workflow_type="initial",
            thread_id=task.id,
            preview_payload={"success": True, "data": {"city": plan.city}},
            native_payload=plan.model_dump(mode="json"),
            validation_report={"issues": []},
            diff_payload={},
            proposed_version=1,
        )

    approval = client.post(
        f"/api/v2/trips/tasks/{created['task_id']}/review",
        json={"action": "approve"},
    )
    assert approval.status_code == 202
    assert approval.json()["review"]["status"] == "approved"

    with db_session_factory() as session:
        task = get_task(session, created["task_id"])
        first = save_trip_version(
            session,
            trip_id=task.trip_id,
            version=1,
            payload={"success": True, "data": {"city": plan.city, "version": 1}},
            planner_engine="journey_graph",
            version_role="primary",
            schema_version="2.0",
            native_payload=plan.model_dump(mode="json"),
            validation_report={"issues": []},
            activate=True,
        )
        changed = plan.model_copy(update={"overall_suggestions": "Version two"})
        save_trip_version(
            session,
            trip_id=task.trip_id,
            version=2,
            payload={"success": True, "data": {"city": plan.city, "version": 2}},
            planner_engine="journey_graph",
            version_role="replan",
            schema_version="2.0",
            native_payload=changed.model_dump(mode="json"),
            parent_version=first.version,
            change_reason="Change suggestion",
            validation_report={"issues": []},
            activate=True,
        )
        task.status = "completed"
        task.result_payload = {"success": True, "data": {"city": plan.city, "version": 2}}
        session.commit()
        trip_id = task.trip_id

    versions = client.get(f"/api/v2/trips/{trip_id}/versions")
    assert versions.status_code == 200
    assert [(item["version"], item["active"]) for item in versions.json()] == [
        (1, False),
        (2, True),
    ]

    compared = client.get(f"/api/v2/trips/{trip_id}/versions/1/compare/2")
    assert compared.status_code == 200
    assert any(
        entry["path"] == "/overall_suggestions"
        for entry in compared.json()["entries"]
    )

    rollback = client.post(
        f"/api/v2/trips/{trip_id}/versions/1/rollback",
        json={"reason": "Restore the accepted baseline."},
    )
    assert rollback.status_code == 200
    assert rollback.json()["version"] == 3
    assert rollback.json()["active"] is True
    assert rollback.json()["version_role"] == "rollback"

    reviews = client.get(f"/api/v2/trips/{trip_id}/reviews")
    assert reviews.status_code == 200
    assert any(item["workflow_type"] == "rollback" for item in reviews.json())


def test_canonical_approve_and_replan_routes(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    created = client.post("/api/v2/trips", json=TRIP_REQUEST_V2_EXAMPLE).json()
    plan = _base_plan()
    with db_session_factory() as session:
        task = get_task(session, created["task_id"])
        assert task is not None
        record_pending_review(
            session,
            task_id=task.id,
            workflow_type="initial",
            thread_id=task.id,
            preview_payload={"success": True, "data": {"city": plan.city}},
            native_payload=plan.model_dump(mode="json"),
            validation_report={"issues": []},
            diff_payload={},
            proposed_version=1,
        )

    approval = client.post(f"/api/v2/trips/{created['trip_id']}/approve")
    assert approval.status_code == 202
    assert approval.json()["review"]["status"] == "approved"

    with db_session_factory() as session:
        task = get_task(session, created["task_id"])
        assert task is not None
        save_trip_version(
            session,
            trip_id=task.trip_id,
            version=1,
            payload={"success": True, "data": {"city": plan.city}},
            planner_engine="journey_graph",
            version_role="primary",
            schema_version="2.0",
            native_payload=plan.model_dump(mode="json"),
            validation_report={"issues": []},
            activate=True,
        )
        task.status = "completed"
        task.result_payload = {"success": True, "data": {"city": plan.city}}
        session.commit()

    replan = client.post(
        f"/api/v2/trips/{created['trip_id']}/replan",
        json={"instruction": "Remove Museum A from day one.", "day_indices": [0]},
    )
    assert replan.status_code == 202
    assert replan.json()["review"]["workflow_type"] == "replan"
    assert replan.json()["review"]["status"] == "requested"
