import json
from types import SimpleNamespace

import pytest
from backend.app.services import travel_place_selection as selection
from backend.app.services.travel_ledger import PlanningInputRequired
from backend.tests.test_one_click_travel import settings


def fake_client(monkeypatch, content, reason="stop", empty_choices=False):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[]
                if empty_choices
                else [
                    SimpleNamespace(finish_reason=reason, message=SimpleNamespace(content=content))
                ],
                usage=SimpleNamespace(prompt_tokens=100, completion_tokens=25),
            )

    monkeypatch.setattr(selection, "OpenAI", Client)
    return calls


def test_selection_uses_configured_output_limit(monkeypatch):
    payload = {
        "attraction_ids": ["A"],
        "restaurant_ids": ["R"],
        "notes": "",
        "unmet_requirements": [],
    }
    calls = fake_client(monkeypatch, json.dumps(payload))
    config = settings().model_copy(update={"llm_structured_max_tokens": 16384})
    assert selection.select_places(config, {}) == {**payload, "requirement_issues": []}
    assert calls[0]["max_tokens"] == 16384
    assert len(calls) == 1


@pytest.mark.parametrize(
    "content,reason,empty,code",
    [
        ("private raw response", "length", False, "model_truncated"),
        (None, "stop", False, "model_empty"),
        ("", "stop", True, "model_empty"),
        ("private raw response", "stop", False, "model_invalid"),
        ('{"attraction_ids": []}', "stop", False, "model_invalid"),
    ],
)
def test_failure_pauses_once_with_safe_diagnostics(
    monkeypatch, content, reason, empty, code, caplog
):
    calls = fake_client(monkeypatch, content, reason, empty)
    with pytest.raises(PlanningInputRequired) as caught:
        selection.select_places(settings(), {})
    assert caught.value.payload["code"] == code
    assert caught.value.payload["provider"] == "model"
    assert caught.value.payload["diagnostics"]["output_tokens"] == 25
    assert "private raw response" not in str(caught.value.payload) + caplog.text
    assert len(calls) == 1
