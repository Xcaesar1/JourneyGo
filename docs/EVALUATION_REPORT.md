# JourneyOps Evaluation Report

## Reproducibility Contract

| Item | Value |
| --- | --- |
| Dataset | `journeyops-travel-v1.0.0` |
| Cases | 36 |
| Evaluator | `journeyops-evaluator/1.0.0` |
| Seed | `20260808` |
| Engines | `legacy`, `journey_graph` |
| Fixture | `journeyops-offline-observations/1.0.0` |
| CI floor | each engine pass rate `>= 0.75` |

The dataset covers domestic and overseas travel, multi-city transfers, weather, closures, reservations,
budget, mobility, duplicate control, provider 429/timeout/auth failures, Worker restart, delayed review,
scoped replan, cache behavior, prompt injection, concurrency and model budget enforcement. Dataset and
observations are immutable repository fixtures; the evaluator rejects missing, duplicate or unexpected
case/engine pairs.

Run from the repository root without network or model calls:

```bash
python -m backend.scripts.run_evaluation \
  --dataset backend/evaluation/datasets/journeyops_v1.json \
  --observations backend/evaluation/fixtures/offline_observations_v1.json \
  --minimum-pass-rate 0.75 \
  --output artifacts/evaluation-report.json
```

## Baseline Result

Execution date: 2026-08-08 Asia/Shanghai.

| Engine | Passed | Pass rate | Mean latency fixture | Total cost fixture |
| --- | ---: | ---: | ---: | ---: |
| legacy | 28 / 36 | 77.78% | 120,000 ms | USD 6.84 |
| journey_graph | 35 / 36 | 97.22% | 91,000 ms | USD 5.04 |

JourneyGraph wins this pinned baseline by pass rate. Latency and cost values are sanitized fixture observations,
not a claim about current provider pricing or live production performance. Real runs persist measured latency and
token usage; dollar cost is calculated only from operator-supplied per-million-token rates.

## Metric Definitions

Each case checks a relevant subset of schema validity, date consistency, budget arithmetic, critical timeline
conflicts, duplicate POIs, source coverage, tool success, retry recovery, checkpoint resume and replan scope
precision. Every case also enforces a latency ceiling and model-cost ceiling. Fault scenarios additionally require
the expected failure class to be detected.

Operational telemetry records `trace_id`, `task_id`, `trip_id`, component, node, tool, status, latency, input/output/
total tokens, calculated cost, retry count, cache hit, model ID, Prompt version, workflow version and tool version.
Prompts, model outputs, request payloads, authorization headers, API keys and Cookies are excluded.

## Known Failures

### Legacy

| Case | Failed assertion | Failure location |
| --- | --- | --- |
| `eval_004` | budget consistency | node `legacy_response_parser` |
| `eval_007` | replan scope precision | node `legacy_replan` |
| `eval_011` | retry recovery, tool success | node `legacy_planner`, tool `web_search` |
| `eval_013` | tool success | tool `xhs_community` |
| `eval_014` | restart resume | node `legacy_planner` |
| `eval_015` | delayed-review resume | node `legacy_planner` |
| `eval_029` | source coverage | tool `web_search` |
| `eval_036` | latency budget | tool `web_search` |

### JourneyGraph

| Case | Failed assertion | Failure location |
| --- | --- | --- |
| `eval_013` | community tool success | node `research`, tool `xhs_community` |

The community-source failure is non-fatal by design: planning continues with explicit unavailable/unknown evidence.
It remains a failed tool-quality assertion so optional provider degradation cannot disappear from regression reports.

## CI Regression Rule

CI executes the evaluator after pytest and uploads `artifacts/evaluation-report.json`. The initial floor is 75%
because the truthful legacy baseline is 77.78%; setting 80% would make the existing comparison engine permanently
red. Lowering the floor, changing fixture defaults, deleting a failure or changing the dataset/evaluator version
requires review. JourneyGraph's higher baseline is reported separately and must not be hidden by the shared floor.

## Limitations

- This committed report is a deterministic offline regression baseline, not an online model leaderboard.
- Provider behavior, pricing and travel facts are time-sensitive; live acceptance must record its model ID, versions,
  trace and measured usage independently.
- LangSmith/Langfuse was intentionally not added. PostgreSQL telemetry satisfies the current localization and audit
  requirements without introducing another external data processor or Secret.
- Staging has no successful Brave Search credential, so the known Noop/fallback research limitation remains.
