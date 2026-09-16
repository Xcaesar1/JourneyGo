# Weather MCP

- Scope: JourneyGraph only; legacy planner and saved trip versions are unchanged.
- Open-Meteo public API is non-commercial only, with attribution and rate limits.
- Install `backend/weather-requirements.lock` into a separate Python 3.10+ venv.
  Do not install its MCP SDK into the main application's environment.
- Docker builds `/opt/weather`; no runtime package downloads are needed.
- Set `WEATHER_ENABLED=true` on both API and Worker. Default is false; demo never calls it.
- `WEATHER_MCP_PYTHON` selects the isolated Python executable (Docker default `/opt/weather/bin/python`).
- Reuse the existing server-side AMap Web Service key to resolve exact administrative cities.
  Currently only unambiguous Chinese city names are supported. Unsupported/ambiguous names
  return unavailable, not the first fuzzy match. No Open-Meteo city-name search is used.
- Convert AMap GCJ-02 centers to approximate WGS84 once at the provider boundary.
- Fetch through MCP `get_weather_forecast` with coordinate strings. Limit results to each
  destination's requested dates. Never fabricate dates beyond the forecast horizon.
- Enrichment overwrites model-generated weather with provider results, including on revision.
- Daily maximum/minimum are not day/night observations. Humidity is unavailable in this
  daily response and is displayed as `--`. No weather-text-based numeric guesses.
- Each weather record preserves source URL and fetch time. The UI links Open-Meteo/CC BY 4.0.
- API change: additive optional weather fields `precipitation_probability`, `humidity`,
  `source_url`, `fetched_at`. No database migration. Existing saved trips are not backfilled.

## Verification

Run `pytest backend/tests/test_weather.py` and the full backend/frontend suites.
Test the image's provider with real AMap credentials without printing keys, then invoke the
graph with a deterministic draft generator to verify weather persists without an LLM charge.
Check the staging UI with a fresh result. Preserve API access protection.

## Rollback

Disable `WEATHER_ENABLED` and recreate staging API and Worker with `--no-deps --no-build`.
For full rollback restore their respective recorded image tags; they may differ.
Do not restart PostgreSQL/Redis, run migrations, change ingress, or overwrite saved data.
Production remains unchanged; migrating the old single-service production is a separate task.

## Staging Release 2026-09-16

- Image: `journeyops-app:weather-20260916-r3`, layered on `mobile-f62e7bd`.
- Release directory: `/opt/tripstar/releases/weather-20260916`.
- The server's original checkout/environment remain unchanged. Use the weather override
  for subsequent recreations; running the old two-file Compose command omits this release.
- Deploy only API and Worker, preserving databases, Redis, volumes and ingress:

```bash
cd /opt/tripstar/JourneyOps-staging
docker compose --env-file .env.staging -f docker-compose.yaml -f docker-compose.staging.yaml \
  -f /opt/tripstar/releases/weather-20260916/weather.compose.yaml \
  up -d --no-deps --no-build worker trip-planner
```

- Roll back using the recorded per-service tags:

```bash
cd /opt/tripstar/JourneyOps-staging
docker compose --env-file .env.staging -f docker-compose.yaml -f docker-compose.staging.yaml \
  -f /opt/tripstar/releases/weather-20260916/rollback.weather.yaml \
  up -d --no-deps --no-build worker trip-planner
```

- The previous API image was `mobile-f62e7bd`; Worker was `attraction-phase2-3108605`.
- Implementation upstream: https://github.com/AiAgentKarl/weather-mcp-server (MIT).
- AMap district lookup supplies the center; Open-Meteo provides weather, not AMap weather.
- `python -m backend.scripts.weather_smoke` runs a real coordinate lookup and MCP forecast
  through a deterministic graph and the API adapter, without LLM requests or database writes.
- `tests/weather-ui.cjs` consumes that JSON via `WEATHER_SMOKE_FILE` and private staging
  Basic Auth via `WEATHER_AUTH_FILE`. It uses isolated browser storage, not saved server trips.
- Local verification: 178 backend tests passed, 4 environment-dependent integration tests
  skipped; 25 frontend tests passed; production frontend build passed. Existing legacy
  asset references/bundle-size build warnings remain.
- Server smoke passed inside the deployed Worker with real Xi'an coordinates and forecasts.
  This does not submit a paid LLM planning task or test a complete queued planning run.
