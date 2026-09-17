import pytest
from backend.app.db.models import TravelQuery, Trip
from backend.app.services.travel_ledger import PlanningInputRequired, QueryLedger
from backend.tests.test_one_click_travel import request
from sqlalchemy import select


def ledger(factory):
    with factory() as session:
        session.add(Trip(id="t", idempotency_key="test", request_payload={}))
        session.commit()
    return QueryLedger("t", request(flight_confirmed=True), factory)


def test_intent_committed_before_dispatch_and_reused(db_session_factory):
    store = ledger(db_session_factory)
    calls = []

    def send():
        with db_session_factory() as session:
            row = session.scalar(select(TravelQuery))
            assert row.status == "dispatching"
            assert row.authorization["max_calls"] == 1
        calls.append(1)
        return {"price": 123}

    assert store.execute("flight", "outbound", {"date": "2026-09-20"}, send) == {"price": 123}
    again = QueryLedger("t", store.request, db_session_factory)
    assert again.execute("flight", "outbound", {"date": "2026-09-20"}, send) == {"price": 123}
    assert len(calls) == 1
    assert store.records[0]["fetched_at"] == again.records[0]["fetched_at"]


@pytest.mark.parametrize("crash", [TimeoutError, KeyboardInterrupt])
def test_uncertain_dispatch_never_automatically_reissued(db_session_factory, crash):
    store = ledger(db_session_factory)
    calls = []

    def send():
        calls.append(1)
        raise crash()

    with pytest.raises((PlanningInputRequired, KeyboardInterrupt)):
        store.execute("flight", "outbound", {}, send)
    with pytest.raises(PlanningInputRequired, match="不会自动重发"):
        QueryLedger("t", store.request, db_session_factory).execute("flight", "outbound", {}, send)
    assert len(calls) == 1


def test_concurrent_duplicate_does_not_send_second_call(db_session_factory):
    store = ledger(db_session_factory)

    def send():
        concurrent = QueryLedger("t", store.request, db_session_factory)
        with pytest.raises(PlanningInputRequired):
            concurrent.execute("flight", "outbound", {}, lambda: pytest.fail("duplicate send"))
        return {"ok": True}

    store.execute("flight", "outbound", {}, send)


def test_refresh_requires_new_consent_and_does_not_invalidate_other_providers(db_session_factory):
    store = ledger(db_session_factory)
    calls = []

    def send():
        calls.append(1)
        return {"ok": True}

    store.execute("flight", "outbound", {}, send)
    store.request.quote_revision = {"hotel": 1}
    store.execute("flight", "outbound", {}, send)
    assert len(calls) == 1
    store.request.quote_revision = {"flight": 1}
    store.request.flight_confirmed = False
    with pytest.raises(PlanningInputRequired):
        store.execute("flight", "outbound", {}, send)
    assert len(calls) == 1
    store.request.flight_confirmed = True
    store.execute("flight", "outbound", {}, send)
    assert len(calls) == 2


def test_explicit_model_revision_preserves_quotes_and_old_failure(db_session_factory):
    store = ledger(db_session_factory)
    for provider in ["train", "flight", "hotel", "amap"]:
        store.execute(provider, "fixture", {}, lambda: {"ok": True})

    def fail():
        raise PlanningInputRequired(
            "model_truncated",
            "retry model",
            provider="model",
            diagnostics={"finish_reason": "length"},
        )

    with pytest.raises(PlanningInputRequired):
        store.execute("model", "place_selection", {}, fail)
    with pytest.raises(PlanningInputRequired) as caught:
        store.execute("model", "place_selection", {}, lambda: pytest.fail("automatic retry"))
    assert caught.value.payload["diagnostics"] == {"finish_reason": "length"}
    store.request.quote_revision["model"] = 1
    for provider in ["train", "flight", "hotel", "amap"]:
        store.execute(provider, "fixture", {}, lambda: pytest.fail("quote repeated"))
    store.execute("model", "place_selection", {}, lambda: {"ok": True})
    with db_session_factory() as session:
        records = session.scalars(select(TravelQuery).where(TravelQuery.provider == "model")).all()
        assert len(records) == 2
        assert {r.status for r in records} == {"blocked", "succeeded"}
        assert all(r.finished_at is not None for r in records)
