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
- Default `AMAP_PERSONAL_MAP_ENABLED=false`; `VITE_AMAP_WEB_KEY` and `API_ACCESS_CODE` must be configured server-side.
- 2026-09-17: read-only `tools/list` using staging credentials verified the tool name and schema (`orgName`, daily `lineList`, `pointInfoList` with name/lon/lat/poiId). No map was created.
- Account remaining quota, billing and entitlement cannot be inferred from `tools/list`. Verify them in the AMap console and obtain approval for any charge/new authorization before enabling the flag. Do not claim unlimited free service.
- Official references: https://developer.amap.com/api/mcp-server/gettingstarted and https://developer.amap.com/api/mcp-server/summary; price field: https://developer.amap.com/api/webservice/guide/api-advanced/newpoisearch.
- Local tests mock external map writes. Live returned-link compatibility and Android app handoff still require an authorized integration check with the app installed. App login/location permissions remain controlled by AMap.
- Rollback: disable the flag first, then revert only this feature's commit after an approved release. Existing itinerary and map ledger data need no migration or deletion.

## Local Verification (2026-09-17)
- Backend suite: 344 passed, 4 skipped. Frontend suite: 47 passed. Production build and changed-file Ruff checks passed; existing asset-resolution/chunk-size build warnings remain.
- Mocked Chrome checks at 360/390/768/1440 px passed: whole/day export, explicit confirmation, recoverable failure/retry, no automatic POST, date scopes and no document horizontal overflow.
- Screenshots: `artifacts/costs-{width}.png`, `artifacts/map-{width}.png`, `artifacts/map-day-{width}.png`. These use local fixtures and mocked map responses, not newly created maps.
- Android `adb devices` returned no connected device. Physical-device app handoff and live map creation are unverified. No commit, deployment, real itinerary creation or review was performed.
