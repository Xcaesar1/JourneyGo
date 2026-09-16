"""Run the pinned offline planner comparison and emit machine-readable results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.evaluation import evaluate_dataset, load_dataset, load_fixture_observations

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "backend" / "evaluation" / "datasets" / "journeyops_v1.json"
DEFAULT_FIXTURE = ROOT / "backend" / "evaluation" / "fixtures" / "offline_observations_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--observations", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--minimum-pass-rate", type=float, default=0.75)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    observations = load_fixture_observations(args.observations, dataset)
    report = evaluate_dataset(dataset, observations)
    rendered = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if all(engine.pass_rate >= args.minimum_pass_rate for engine in report.engines) else 1


if __name__ == "__main__":
    raise SystemExit(main())
