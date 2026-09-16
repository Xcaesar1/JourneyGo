"""Deterministic evaluator for exported legacy and JourneyGraph observations."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import (
    CaseEvaluation,
    EngineEvaluation,
    EvaluationCase,
    EvaluationDataset,
    EvaluationObservation,
    EvaluationReport,
)

EVALUATOR_VERSION = "journeyops-evaluator/1.0.0"


def load_dataset(path: Path) -> EvaluationDataset:
    """Load and validate the pinned dataset without executing network calls."""
    return EvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))


def load_fixture_observations(
    path: Path,
    dataset: EvaluationDataset,
) -> list[EvaluationObservation]:
    """Expand compact engine defaults plus per-case overrides into observations."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    defaults = payload["defaults"]
    overrides = payload.get("overrides", {})
    observations: list[EvaluationObservation] = []
    for case in dataset.cases:
        for engine in ("legacy", "journey_graph"):
            values: dict[str, Any] = deepcopy(defaults[engine])
            values.update(overrides.get(case.case_id, {}).get(engine, {}))
            observations.append(
                EvaluationObservation(case_id=case.case_id, engine=engine, **values)
            )
    return observations


def evaluate_dataset(
    dataset: EvaluationDataset,
    observations: list[EvaluationObservation],
) -> EvaluationReport:
    """Evaluate exactly one observation per case and engine."""
    case_map = {case.case_id: case for case in dataset.cases}
    expected_keys = {
        (case.case_id, engine)
        for case in dataset.cases
        for engine in ("legacy", "journey_graph")
    }
    observation_map = {(item.case_id, item.engine): item for item in observations}
    if set(observation_map) != expected_keys or len(observation_map) != len(observations):
        missing = sorted(expected_keys - set(observation_map))
        unexpected = sorted(set(observation_map) - expected_keys)
        raise ValueError(f"Observation coverage mismatch; missing={missing}, unexpected={unexpected}")

    engine_reports: list[EngineEvaluation] = []
    for engine in ("legacy", "journey_graph"):
        results = [
            _evaluate_case(case_map[case_id], observation_map[(case_id, engine)])
            for case_id in sorted(case_map)
        ]
        engine_observations = [observation_map[(case_id, engine)] for case_id in sorted(case_map)]
        passed_cases = sum(result.passed for result in results)
        engine_reports.append(
            EngineEvaluation(
                engine=engine,
                case_count=len(results),
                passed_cases=passed_cases,
                pass_rate=round(passed_cases / len(results), 4),
                average_latency_ms=round(
                    sum(item.latency_ms for item in engine_observations) / len(results), 2
                ),
                total_model_cost_usd=round(
                    sum(item.model_cost_usd for item in engine_observations), 6
                ),
                cases=results,
            )
        )

    ranked = sorted(
        engine_reports,
        key=lambda item: (-item.pass_rate, item.total_model_cost_usd, item.average_latency_ms),
    )
    winner = ranked[0].engine if ranked[0].pass_rate != ranked[1].pass_rate else None
    return EvaluationReport(
        dataset_version=dataset.dataset_version,
        evaluator_version=EVALUATOR_VERSION,
        seed=dataset.seed,
        engines=engine_reports,
        winner=winner,
    )


def _evaluate_case(
    case: EvaluationCase,
    observation: EvaluationObservation,
) -> CaseEvaluation:
    checks = {
        "schema_valid": observation.schema_valid,
        "date_consistent": observation.date_consistent,
        "budget_consistent": observation.budget_consistent,
        "no_critical_conflicts": observation.critical_conflicts == 0,
        "no_duplicate_pois": observation.duplicate_pois == 0,
        "source_coverage": observation.source_coverage >= 0.6,
        "tool_success": observation.tool_success_rate >= 0.8,
        "retry_recovered": observation.retry_recovered,
        "resume_success": observation.resume_success,
        "replan_scope_precise": observation.replan_scope_precision >= 0.8,
    }
    failed: list[str] = [assertion for assertion in case.assertions if not checks[assertion]]
    for issue in case.expected_detections:
        if issue not in observation.detected_issues:
            failed.append(f"detects:{issue}")
    if observation.latency_ms > case.max_latency_ms:
        failed.append("latency_budget")
    if observation.model_cost_usd > case.max_cost_usd:
        failed.append("model_cost_budget")
    total = len(case.assertions) + len(case.expected_detections) + 2
    return CaseEvaluation(
        case_id=case.case_id,
        engine=observation.engine,
        passed=not failed,
        passed_assertions=total - len(failed),
        total_assertions=total,
        failed_assertions=failed,
        failure_node=observation.failure_node,
        failure_tool=observation.failure_tool,
    )
