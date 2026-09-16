"""Phase 7 offline evaluation contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.app.evaluation import evaluate_dataset, load_dataset, load_fixture_observations

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "backend" / "evaluation" / "datasets" / "journeyops_v1.json"
FIXTURE = ROOT / "backend" / "evaluation" / "fixtures" / "offline_observations_v1.json"


def test_dataset_has_realistic_minimum_and_stable_ids() -> None:
    dataset = load_dataset(DATASET)

    assert len(dataset.cases) == 36
    assert len({case.case_id for case in dataset.cases}) == 36
    assert {"provider_failure", "replan", "durability", "input_safety"}.issubset(
        {case.category for case in dataset.cases}
    )


def test_offline_fixture_compares_both_engines_and_locates_failures() -> None:
    dataset = load_dataset(DATASET)
    report = evaluate_dataset(dataset, load_fixture_observations(FIXTURE, dataset))
    engines = {item.engine: item for item in report.engines}

    assert set(engines) == {"legacy", "journey_graph"}
    assert all(item.case_count == 36 for item in engines.values())
    assert engines["journey_graph"].pass_rate > engines["legacy"].pass_rate
    failures = [case for item in report.engines for case in item.cases if not case.passed]
    assert any(case.failure_node for case in failures)
    assert any(case.failure_tool for case in failures)


def test_evaluator_rejects_partial_observation_coverage() -> None:
    dataset = load_dataset(DATASET)
    observations = load_fixture_observations(FIXTURE, dataset)

    with pytest.raises(ValueError, match="coverage mismatch"):
        evaluate_dataset(dataset, observations[:-1])
