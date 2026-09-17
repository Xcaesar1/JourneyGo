"""Commit intent before sending a supplier request, fail closed on ambiguous outcomes."""

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db.models import TravelQuery, TripTask
from ..db.session import SessionLocal


class PlanningInputRequired(ValueError):
    def __init__(self, code, message, *, provider=None, diagnostics=None):
        super().__init__(message)
        self.payload = {"code": code, "message": message, "provider": provider}
        if diagnostics is not None:
            self.payload["diagnostics"] = diagnostics


class QueryReuseUnavailable(PlanningInputRequired):
    """Stop model-only recovery from expanding its supplier query set."""

    def __init__(self, provider, scope):
        super().__init__(
            "query_not_previously_verified",
            "本次恢复仅复用已核实的查询结果；如需新查询，请明确更新对应报价。",
            provider=provider,
            diagnostics={"scope": scope},
        )


class QueryLedger:
    def __init__(self, trip_id, request, session_factory=SessionLocal):
        self.trip_id = trip_id
        self.request = request
        self.sessions = session_factory
        self.records = []

    def execute(self, provider, scope, arguments, call):
        revision = self.request.quote_revision.get(provider, 0)
        identity = [self.trip_id, provider, scope, arguments, revision]
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        with self.sessions() as session:
            task = session.scalar(select(TripTask).where(TripTask.trip_id == self.trip_id))
            if task is not None and task.cancel_requested:
                raise PlanningInputRequired("cancelled", "任务已取消，不再发起查询。")
            row = session.get(TravelQuery, key)
            if row is None:
                if (
                    provider != "model"
                    and self.request.quote_revision.get("model", 0) > 0
                    and revision == 0
                ):
                    raise QueryReuseUnavailable(provider, scope)
                if provider == "flight" and not self.request.flight_confirmed:
                    raise PlanningInputRequired(
                        "flight_consent", "请确认本次往返航班查询。", provider=provider
                    )
                row = TravelQuery(
                    id=key,
                    trip_id=self.trip_id,
                    provider=provider,
                    scope=scope,
                    arguments=arguments,
                    status="dispatching",
                    authorization={
                        "flight_confirmed": self.request.flight_confirmed,
                        "revision": revision,
                        "max_calls": 1,
                    },
                )
                session.add(row)
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    row = session.get(TravelQuery, key)
                    return self._reuse(row)
            else:
                return self._reuse(row)
        try:
            result = call()
        except PlanningInputRequired as exc:
            with self.sessions() as session:
                row = session.get(TravelQuery, key)
                row.status, row.result = "blocked", exc.payload
                row.finished_at = datetime.now(timezone.utc)
                session.commit()
            raise
        except Exception:
            with self.sessions() as session:
                row = session.get(TravelQuery, key)
                row.status = "uncertain"
                session.commit()
            raise PlanningInputRequired(
                "supplier_uncertain",
                "查询结果不确定，已停止自动重试。请调整条件或明确更新报价。",
                provider=provider,
            ) from None
        # A crash before this commit leaves dispatching, which is also non-retryable.
        with self.sessions() as session:
            row = session.get(TravelQuery, key)
            row.result = result
            row.status = "succeeded"
            row.finished_at = datetime.now(timezone.utc)
            session.commit()
            return self._reuse(row)

    def _reuse(self, row):
        if row is not None and row.status == "blocked":
            raise PlanningInputRequired(
                row.result["code"],
                row.result["message"],
                provider=row.provider,
                diagnostics=row.result.get("diagnostics"),
            )
        if row is None or row.status != "succeeded":
            raise PlanningInputRequired(
                "supplier_uncertain",
                "已有查询可能已发出，不会自动重发。",
                provider=row.provider if row else None,
            )
        self.records.append(
            {
                "query_id": row.id,
                "provider": row.provider,
                "scope": row.scope,
                "source_url": {
                    "train": "https://www.12306.cn/",
                    "flight": "https://mcp.variflight.com/",
                    "hotel": "https://mcp.rollinggo.cn/mcp",
                    "amap": "https://www.amap.com/",
                }.get(row.provider),
                "fetched_at": row.finished_at.replace(tzinfo=timezone.utc).isoformat(),
            }
        )
        return row.result
