# ADR 0002: Demo, Secret And Release Boundaries

- Status: Accepted
- Date: 2026-08-08
- Scope: Phase 8

## Context

A recruiter must be able to run the project without purchasing model or map access. At the same time, a public
deployment must not serialize model keys, map Web Service keys or community Cookies to anonymous browsers. The
previous runtime settings endpoint mixed browser preferences with server credentials and therefore could not be
published safely.

## Decision

- `DEMO_MODE=true` selects a deterministic typed plan generator and Noop external providers.
- Demo still uses PostgreSQL, Redis, Celery, JourneyGraph, deterministic validation and human review.
- `GET /api/settings` returns only browser-safe values and boolean configuration status.
- Runtime Secret mutation is disabled by default and, when explicitly enabled, requires the API access code.
- Browser AMap JS credentials are runtime public credentials and must be domain-restricted; backend Provider
  credentials never enter the frontend bundle or settings response.
- Production API docs are disabled by default. Demo may enable them explicitly.
- Demo, staging and production use distinct Compose project names, ports and named volumes.

## Consequences

- The keyless demo proves orchestration and product flow, not live provider quality or current travel facts.
- Operators may rotate the AMap browser JS Key or security code without rebuilding the application image.
- Provider readiness is visible without revealing credential values.
- A public release can be reviewed without distributing paid credentials or personal Cookies.
