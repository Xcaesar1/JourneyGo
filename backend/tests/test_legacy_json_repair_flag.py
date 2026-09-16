"""Behavior checks for the temporary legacy JSON repair fallback."""

from __future__ import annotations

import json
from typing import Any

import pytest
from backend.app.agents.legacy.trip_planner_agent import MultiAgentTripPlanner
from backend.app.config import settings
from backend.app.models.schemas import TripPlan, TripRequest


def _request() -> TripRequest:
    return TripRequest(
        city="Tokyo",
        start_date="2026-10-10",
        end_date="2026-10-10",
        travel_days=1,
        transportation="public transit",
        accommodation="midscale hotel",
    )


def _plan_payload() -> dict[str, Any]:
    return {
        "city": "Tokyo",
        "cities": ["Tokyo"],
        "start_date": "2026-10-10",
        "end_date": "2026-10-10",
        "days": [
            {
                "date": "2026-10-10",
                "day_index": 0,
                "city": "Tokyo",
                "description": "Arrival day",
                "transportation": "public transit",
                "accommodation": "midscale hotel",
            }
        ],
        "overall_suggestions": "Keep the first day light.",
    }


def _planner_without_external_dependencies() -> MultiAgentTripPlanner:
    return object.__new__(MultiAgentTripPlanner)


def test_valid_legacy_json_does_not_use_repair_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "legacy_json_repair", False)
    planner = _planner_without_external_dependencies()

    def fail_if_called(*_args: Any, **_kwargs: Any) -> str:
        raise AssertionError("legacy repair chain must not run")

    monkeypatch.setattr(planner, "_sanitize_json_str", fail_if_called)
    monkeypatch.setattr(planner, "_fix_unescaped_quotes", fail_if_called)
    monkeypatch.setattr(planner, "_repair_truncated_json", fail_if_called)
    monkeypatch.setattr(planner, "_llm_repair_json", fail_if_called)

    result = planner._parse_response(json.dumps(_plan_payload()), _request())

    assert isinstance(result, TripPlan)


def test_invalid_legacy_json_fails_when_repair_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "legacy_json_repair", False)
    planner = _planner_without_external_dependencies()

    def fail_if_called(*_args: Any, **_kwargs: Any) -> str:
        raise AssertionError("legacy repair chain must not run")

    monkeypatch.setattr(planner, "_sanitize_json_str", fail_if_called)
    monkeypatch.setattr(planner, "_fix_unescaped_quotes", fail_if_called)
    monkeypatch.setattr(planner, "_repair_truncated_json", fail_if_called)
    monkeypatch.setattr(planner, "_llm_repair_json", fail_if_called)

    with pytest.raises(ValueError, match="repair is disabled"):
        planner._parse_response('{"city": "Tokyo",}', _request())


def test_legacy_repair_chain_remains_available_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "legacy_json_repair", True)
    planner = _planner_without_external_dependencies()
    payload = json.dumps(_plan_payload())
    malformed = payload[:-1] + ",}"

    result = planner._parse_response(malformed, _request())

    assert isinstance(result, TripPlan)
