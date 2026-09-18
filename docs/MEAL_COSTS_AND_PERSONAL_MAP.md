# Meal Costs and Personal Map

## Behavior
- One-click planning uses existing AMap `business.cost` as per-person reference prices. Missing/invalid prices are excluded, never a fixed CNY 60 allowance.
- `Meal.price_reference` is optional: positive `amount_cents`, `source=amap`, `source_url`, `fetched_at`. Native and legacy adapters preserve it. Legacy integer amounts are not authoritative for these meals.
- `travel_summary.cost_items` remains authoritative in cents. `meal_pricing_policy=amap_reference_only`, `costs_complete=false`, and `excluded_costs` identify incomplete costs. Historical snapshots are not rewritten.
- Budget scope shows transport dates, stay span/nights, or whole trip. Whole-trip entries sort after dated entries in both directions.

## Personal Map API
- POST `/api/v2/tasks/{task_id}/personal-map`: `confirmed=true`, exactly one of `version` or `review_id`, optional zero-based `day_index` (null means whole trip).
- Requires the existing shared `X-Access-Code`, including when ordinary read APIs are public. This project has shared-access authentication, not per-user ownership; do not treat task IDs as user isolation.
- Reads only persisted, matching snapshots; no client-supplied coordinates or arbitrary supplier URLs. Invalid/missing coordinates or POI IDs are explicitly omitted.
- Uses official `maps_schema_personal_map` via Streamable HTTP. Existing `TravelQuery` rows store intent before external dispatch and reuse successful results by snapshot/scope/content digest. No migration.
- Errors before dispatch (disabled, invalid snapshot, no locations) can be retried after correction. Ambiguous dispatch/timeouts are not blindly retried: an operator must check whether a map was created before resolving the ledger row. Never delete uncertain rows simply to retry.
- No map is created during planning, loading or section switching. A confirmation and a separate app-open gesture are required.

## Enablement and Verification
- 2026-09-18 authorized live check: created one map for the saved Shanghai itinerary's
  2026-09-21 day (six points, none omitted), through the existing durable export ledger.
  The returned `amapuri://workInAmap/createWithToken` link opened on the connected
  Android AMap app and rendered the named map, markers and daily route. No purchase,
  new permission or fee prompt appeared; this does not establish zero billing.
  That initial check overrode the flag only in its one-off process. The subsequent
  staging configuration release persistently enabled the website flag; see
  `AMAP_ENABLEMENT_HANDOFF.md` and the API-only rollback in `DEPLOYMENT.md`.
  Do not replay map creation with a different version/review identity to test opening.
- The capability endpoint exposes `personal_map.enabled`. The export panel checks it
  before offering creation and explains disabled state without sending a POST.
- Default `AMAP_PERSONAL_MAP_ENABLED=false`; `VITE_AMAP_WEB_KEY` and `API_ACCESS_CODE` must be configured server-side.
- 2026-09-17: read-only `tools/list` using staging credentials verified the tool name and schema (`orgName`, daily `lineList`, `pointInfoList` with name/lon/lat/poiId). No map was created.
- Account remaining quota, billing and entitlement cannot be inferred from `tools/list`. Verify them in the AMap console and obtain approval for any charge/new authorization before enabling the flag. Do not claim unlimited free service.
- Official references: https://developer.amap.com/api/mcp-server/gettingstarted and https://developer.amap.com/api/mcp-server/summary; price field: https://developer.amap.com/api/webservice/guide/api-advanced/newpoisearch.
- Local tests mock external map writes. The subsequent real Android Chrome button
  round trip passed twice on staging, reusing the exact existing map with an unchanged
  ledger. Production remains out of scope. App permissions remain controlled by AMap.
- Rollback: disable the flag first, then revert only this feature's commit after an approved release. Existing itinerary and map ledger data need no migration or deletion.

## Local Verification (2026-09-17)
- Backend suite: 344 passed, 4 skipped. Frontend suite: 47 passed. Production build and changed-file Ruff checks passed; existing asset-resolution/chunk-size build warnings remain.
- Mocked Chrome checks at 360/390/768/1440 px passed: whole/day export, explicit confirmation, recoverable failure/retry, no automatic POST, date scopes and no document horizontal overflow.
- Screenshots: `artifacts/costs-{width}.png`, `artifacts/map-{width}.png`, `artifacts/map-day-{width}.png`. These use local fixtures and mocked map responses, not newly created maps.
- Android `adb devices` returned no connected device. Physical-device app handoff and live map creation are unverified. No commit, deployment, real itinerary creation or review was performed.
