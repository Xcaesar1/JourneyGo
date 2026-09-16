# Phase 8 Acceptance

## Scope

Phase 8 packages JourneyOps for recruiter review. It does not deploy or modify production, publish a release, or
start another phase. The legacy Planner implementation remains unchanged.

## Delivered

- Complete request constraints in the Vue form: origin, budget, travelers, pace, daily window and walking limit.
- API v2 submission, real Worker/JourneyGraph progress events, structured retry and diagnostic trace ID.
- Existing source, transport, validation, human review, version, diff and rollback views retained.
- Deterministic keyless Demo mode with isolated Compose port and volumes.
- Browser-safe runtime settings; server Secret mutation disabled by default and access-code guarded when enabled.
- AMap-only browser map path with domain-restricted browser credentials loaded from the browser-safe runtime
  settings endpoint; credentials are not embedded in Docker build arguments or image layers.
- Container log rotation, resource limits, health checks and non-root application runtime.
- Chinese/English README, Before/After architecture, upstream changelog, ADR, HTTPS examples and demo script.

## Acceptance Evidence

| Check | Evidence | Status |
| --- | --- | --- |
| Frontend production build | `npm run build` | Passed |
| Compose demo config | base + `docker-compose.demo.yaml` | Passed |
| Compose staging config | base + `docker-compose.staging.yaml` | Passed |
| Backend tests | `145 passed, 4 skipped`; 17 existing deprecation warnings | Passed |
| CI lint gates | architecture Ruff, critical Ruff and changed-file Ruff | Passed |
| Offline 36-case evaluation | legacy `28/36`; journey_graph `35/36` | Passed |
| Frontend browser flow | form, WebSocket progress, review, approve, V1; console `0` errors / `0` warnings | Passed |
| Keyless end-to-end demo | Oracle isolated stack on `127.0.0.1:17862` | Passed |
| Oracle staging | final image `journeyops-app:phase8-f6ec417`; API/Worker healthy as `journeyops` | Passed |
| Screenshots | `docs/assets/phase8/01-form.png` through `04-version.png` | Passed |
| Production isolation | original container ID, image, restart count and home hash unchanged | Passed |
| GitHub CI | run `31260998555` for `f6ec417` | Passed |
| Release tag | `v3.0.0-rc.1` on verified commit `07c9717` | Published as GitHub Prerelease |

## Oracle Evidence

- Pre-deploy backup: `/var/backups/tripstar/20260808T132203Z-phase8-predeploy`; repository bundle, PostgreSQL
  custom dump, image manifest and SHA-256 manifest all verified. Directory mode is `0700`; files are `0600`.
- Staging: `127.0.0.1:17861`, image `journeyops-app:phase8-f6ec417`, Alembic `20260808_05 (head)`, readiness
  `200`, API/Worker restart counts `0`, and no recent `Traceback`, `CRITICAL` or permission-denied lines.
- Demo: `127.0.0.1:17862`, independent PostgreSQL/Redis/data volumes, readiness `200`, model/provider keys not
  required, and API/Worker both run as the non-root `journeyops` user.
- Real demo task: `task_0ef1915e09cc44379ef5`, trip `trip_8e13c1a1ea9f40eb9670`, trace
  `trace_594bbf3d7f3f4fa3873c688764090998`.
- Observed stages: queued, initializing, workflow start, normalize request, prepare research, research web,
  collect, transport, draft, enrich plan, validate, human review, awaiting approval, review resume, persist and
  graph building, completed.
- Approval boundary: zero versions before approval; one active immutable version after approval; model input
  plus output tokens remained `0`; the result identifies deterministic Demo mode.
- Production remained `200` on `127.0.0.1:17860`. Container
  `3e6848a91f74c88d47500cad16c083a53cfe42d2ee89c6694ca8e933860da851`, image
  `tripstar-trip-planner`, restart count `0`, and home SHA-256
  `15a17d2170fe8caf50a7d6e4ba4e6565116a830d5ecc5595516cc416485fc09c` are unchanged.

## Browser Evidence

Playwright exercised the production frontend code against a controlled sanitized API/WebSocket fixture so visual
review was independent of the intermittent SSH tunnel. The remote end-to-end evidence above separately verifies
the real backend path. The browser submitted the full form, displayed actual JourneyGraph stage events, entered
the human checkpoint, approved the draft and displayed active immutable V1. Final browser console output had no
errors or warnings.

## Residual Risks

- **P0:** none found in Phase 8 implementation or isolated staging/demo deployment.
- **P1:** the main frontend bundle remains about 3.1 MB minified and should be split before high-traffic public
  promotion. Existing theme asset references are unresolved at build time and use runtime fallback behavior.
- **P2:** full-repository Ruff still reports 162 pre-existing issues concentrated in legacy and older service
  code. CI-critical, architecture and changed-file gates pass. Existing Pydantic/Starlette deprecation warnings
  should be addressed separately without rewriting the protected legacy planner.

## Release Boundary

The repository owner approved `v3.0.0-rc.1`; the annotated tag remains fixed on verified commit `07c9717` and
the GitHub Release is published as a prerelease. This approval does not authorize production promotion, legacy
data migration or movement of the release tag.
