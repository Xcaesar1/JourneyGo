"""Tests for native JSON output into the TripPlanV2 contract."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from backend.app.agents.journey_graph.nodes import build_placeholder_plan, normalize_request
from backend.app.agents.journey_graph.structured_output import (
    DemoPlanGenerator,
    NativeJsonPlanGenerator,
    StructuredPlanGenerationError,
    build_configured_plan_generator,
)
from backend.app.config import settings
from backend.app.domain.trip_models import TRIP_REQUEST_V2_EXAMPLE, TripPlanV2


class FakeCompletions:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        content = self.contents[min(len(self.calls) - 1, len(self.contents) - 1)]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=content),
                )
            ]
        )


class FakeClient:
    def __init__(self, contents: list[str]) -> None:
        self.completions = FakeCompletions(contents)
        self.chat = SimpleNamespace(completions=self.completions)


def _normalized_state() -> dict[str, Any]:
    state = {
        "trip_id": "trip_structured_test",
        "task_id": "task_structured_test",
        "request": TRIP_REQUEST_V2_EXAMPLE,
    }
    state.update(normalize_request(state))
    return state


def _valid_plan_json() -> str:
    return build_placeholder_plan(_normalized_state()).model_dump_json()


def test_native_json_generator_requests_provider_json_mode() -> None:
    client = FakeClient([_valid_plan_json()])
    generator = NativeJsonPlanGenerator(client, "structured-test-model", max_attempts=1)

    result = generator(_normalized_state())

    assert isinstance(result, TripPlanV2)
    request = client.completions.calls[0]
    assert request["response_format"] == {"type": "json_object"}
    assert "TripPlanV2 JSON Schema" in request["messages"][0]["content"]
    assert request["messages"][1]["content"].startswith("Create the TripPlanV2 JSON object")


def test_thirty_structured_outputs_have_no_parse_error() -> None:
    client = FakeClient([_valid_plan_json()])
    generator = NativeJsonPlanGenerator(client, "structured-test-model", max_attempts=1)

    results = [generator(_normalized_state()) for _ in range(30)]

    assert len(results) == 30
    assert all(isinstance(result, TripPlanV2) for result in results)
    assert len(client.completions.calls) == 30


def test_invalid_json_retries_the_whole_structured_request() -> None:
    client = FakeClient(["not json", _valid_plan_json()])
    generator = NativeJsonPlanGenerator(client, "structured-test-model", max_attempts=2)

    result = generator(_normalized_state())

    assert isinstance(result, TripPlanV2)
    assert len(client.completions.calls) == 2


def test_invalid_output_raises_redacted_typed_error() -> None:
    sensitive_invalid_output = "not-json-sk-sensitive-value"
    client = FakeClient([sensitive_invalid_output])
    generator = NativeJsonPlanGenerator(client, "structured-test-model", max_attempts=1)

    with pytest.raises(StructuredPlanGenerationError) as captured:
        generator(_normalized_state())

    assert sensitive_invalid_output not in str(captured.value)
    assert "json_invalid" in str(captured.value)


def test_demo_generator_needs_no_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "openai_api_key", "")

    generator = build_configured_plan_generator()
    plan = generator(_normalized_state())

    assert isinstance(generator, DemoPlanGenerator)
    assert plan.schema_version == "2.0"
    assert len(plan.days) == 5
    assert all("demo" in day.attractions[0].name.casefold() for day in plan.days)
    assert generator.last_metrics["total_tokens"] == 0
    assert generator.last_metrics["model_cost_usd"] == 0
