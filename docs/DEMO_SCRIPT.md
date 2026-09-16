# JourneyOps 3–5 Minute Demo

## Preparation

1. Start the keyless demo with the README command and confirm both health endpoints return success.
2. Open `http://127.0.0.1:17862` in a clean browser window.
3. Keep `docs/EVALUATION_REPORT.md` and `docs/ARCHITECTURE.md` ready in adjacent tabs.

## 0:00–0:40 — Product Problem

Explain that ordinary itinerary generators return one opaque answer. JourneyOps treats planning as a durable,
reviewable execution workflow: external facts have sources, computed constraints are validated, and changes are
scoped rather than regenerating everything.

## 0:40–1:30 — Submit A Realistic Request

Enter an origin, one or more destinations, date, budget, traveler count, pace, daily time window and walking
limit. Submit and point out that the UI is displaying Worker-emitted JourneyGraph node events rather than a fake
timer. The demo-only `0.35s` node display window makes each real transition visible; live mode adds no delay.
Mention that the Demo badge means external Provider calls are intentionally disabled.

## 1:30–2:30 — Inspect And Approve

Open the generated draft. Show origin-to-destination transport, daily schedule, source freshness or explicit
unknown evidence, deterministic validation severity and calculated budget. Explain that this is not yet an
immutable version. Approve it and show version 1.

## 2:30–3:30 — Scoped Replanning

Request one focused change, such as reducing day 2 intensity. Show the structured diff and unchanged-day count.
Approve the proposal, compare versions 1 and 2, then explain that rollback appends another version rather than
rewriting history.

## 3:30–4:15 — Reliability And Diagnosis

Show the task/trip/trace identifiers and explain PostgreSQL canonical state, Redis/Celery delivery and database
reconciliation. If a test failure is being demonstrated, use the retry action and diagnostic ID; do not expose raw
Provider exceptions.

## 4:15–5:00 — Evidence

Show the Before/After architecture and the pinned 36-case evaluation. State both results: legacy `28/36`
(`77.78%`) and JourneyGraph `35/36` (`97.22%`). Explicitly call out the remaining JourneyGraph community-source
failure and that latency/cost values are sanitized fixtures, not live pricing claims.
