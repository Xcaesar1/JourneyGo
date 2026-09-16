"""Run a redacted repeatability check against the configured structured model."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from backend.app.agents.journey_graph.nodes import normalize_request
from backend.app.agents.journey_graph.structured_output import (
    StructuredPlanGenerationError,
    build_structured_plan_generator,
)

EVALUATION_REQUEST = {
    "origin": "Shanghai",
    "destinations": [{"city": "Hangzhou", "days": 1}],
    "start_date": "2026-10-10",
    "end_date": "2026-10-10",
    "travel_days": 1,
    "budget_total": "1000.00",
    "currency": "CNY",
    "travelers": 1,
    "transport_preferences": ["train", "public transit"],
    "accommodation_preference": "midscale hotel",
    "interests": ["food", "museums"],
    "pace": "balanced",
    "daily_start_time": "09:00:00",
    "daily_end_time": "20:00:00",
    "language": "en",
    "timezone": "Asia/Shanghai",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.runs <= 100:
        parser.error("--runs must be between 1 and 100")
    if not 1 <= args.concurrency <= 10:
        parser.error("--concurrency must be between 1 and 10")
    return args


def _evaluate_once(generator: Any, state: dict[str, Any]) -> str | None:
    try:
        generator(state)
        return None
    except StructuredPlanGenerationError:
        return "structured_generation_error"
    except Exception as exc:
        return f"unexpected:{type(exc).__name__}"


def main() -> int:
    args = _parse_args()
    generator = build_structured_plan_generator()
    state = {
        "trip_id": "structured-output-evaluation",
        "task_id": "structured-output-evaluation",
        "request": EVALUATION_REQUEST,
    }
    state.update(normalize_request(state))

    failures: Counter[str] = Counter()
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=min(args.concurrency, args.runs)) as executor:
        outcomes = executor.map(
            lambda _: _evaluate_once(generator, state),
            range(args.runs),
        )
        for failure_type in outcomes:
            if failure_type is not None:
                failures[failure_type] += 1

    valid = args.runs - sum(failures.values())

    result = {
        "runs": args.runs,
        "concurrency": args.concurrency,
        "valid_trip_plan_v2": valid,
        "failures": sum(failures.values()),
        "failure_types": dict(sorted(failures.items())),
        "uncaught_json_parse_errors": failures.get("unexpected:JSONDecodeError", 0),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if valid == args.runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
