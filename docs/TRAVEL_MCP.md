# Travel MCP Queries

## Scope

- Add on-demand train, hotel and flight queries to the result page, separate from planning estimates and budget totals. Do not rewrite saved versions.
- Never run paid searches during generation, graph retries, page loads or background refreshes.
- Do not create orders, reserve rooms, buy tickets or collect identity/payment data.
- No PostgreSQL migration. Redis stores five-minute quote snapshots, one-minute deduplication leases and a non-expiring flight call counter.

## Providers

| Provider | Runtime | Allowed tool |
| --- | --- | --- |
| [12306 MCP](https://github.com/Joooook/12306-mcp) | `12306-mcp@0.3.10`, Node stdio | `get-tickets` |
| [RollingGo](https://github.com/RollingGo-AI/rollinggo-hotel-mcp) | `https://mcp.rollinggo.cn/mcp`, Streamable HTTP | `searchHotels` |
| [Variflight](https://www.modelscope.cn/mcp/servers/@variflight-ai/variflight-mcp) | `@variflight-ai/variflight-mcp@1.0.3`, Node stdio | `getFlightPriceByCities` |

Reuse the isolated weather MCP SDK environment (`mcp==1.30.0`), not the legacy application's SDK. The bridge accepts a provider enum and structured arguments, never an arbitrary command, endpoint or tool. Forward only the selected credential. Suppress upstream errors and process stderr; never expose them in responses or logs.

## API

- `GET /api/v2/travel/capabilities`: enabled/paid flags only; no credentials or account identifiers.
- `POST /api/v2/travel/search`: bounded single-provider query, bridge deadline 45 seconds, no automatic retry.
- Request: `provider` (`train|hotel|flight`), `origin`, `destination`, `date` (`YYYY-MM-DD`), `country` (hotel), `nights` (1-28), `adults` (1-4 per room), `high_speed_only`, `confirm_paid`.
- Flight origin/destination require uppercase IATA **city** codes. Provider examples: BJS, SHA, CAN, HFE. UI accepts other verified codes manually; do not guess mappings.
- Flights require valid `X-Access-Code` even when general access protection is disabled, plus `confirm_paid=true` on every submission. Train/hotel respect general access protection and rate limits.
- Response: status/message, normalized offers, source title/URL/domain/trust, fetched_at, cached, effective query. Provider failures return safe statuses (`disabled`, `unavailable`, `busy`, `budget_exhausted`); authentication/validation/rate limits use HTTP 401/422/429.
- Successful empty results have `status=empty` and a timestamp. Unknown prices remain null, never zero.

## Price And Date Semantics

- Train: Asia/Shanghai dates, today through today+14 inclusive. Availability may still be unpublished. The unofficial MCP adapter does not guarantee inventory.
- Hotel: one room, specified adults, no children/multiple-room combinations. `price.lowestPrice` is the **whole-stay starting price**, not a nightly rate. Never multiply it by nights again. Default to one night, requiring user review; a travel day is not automatically a hotel night.
- Flight: lowest returned available cabin per flight, at most five offers. Price is not an all-in fare. Taxes, baggage and cancellation conditions are unverified. Show times in Asia/Shanghai.
- Ignore provider HTML, tracking URLs and arbitrary booking links. Expose only the fixed official 12306 link in offers.
- Cached results retain the original fetch timestamp; they do not hold prices or inventory.

## Configuration And Spending

Configure only in an untracked environment file:

```dotenv
TRAVEL_TRAIN_ENABLED=true
TRAVEL_HOTEL_ENABLED=true
ROLLINGGO_API_KEY=replace-with-private-key
TRAVEL_FLIGHT_ENABLED=false
VARIFLIGHT_API_KEY=replace-with-private-key
TRAVEL_FLIGHT_CALL_LIMIT=0
API_ACCESS_CODE=replace-with-private-access-code
API_RATE_LIMIT_ENABLED=true
```

- After explicit spending approval, enable flights and set `TRAVEL_FLIGHT_CALL_LIMIT` to the approved **cumulative call ceiling**. This is not money or a daily reset.
- Redis key `journeyops:travel:flight:calls:<credential-digest>` is atomic and non-expiring. Reserve before calling; timeouts/errors still consume a slot because charging may have occurred. Cache hits cost no slot. Never automatically refund or retry.
- Raising the configured ceiling grants additional calls; it does not reset usage. Changing credentials starts a separate counter. Do not delete counters to bypass limits.
- Fail closed if Redis is unavailable. Persist Redis; disable flights during Redis data loss/restore, reconcile the supplier portal, then explicitly approve a new ceiling. Counters cover this application only, not earlier diagnostics or other clients.
- Key configuration alone cannot enable paid calls. Committed examples keep flights off and ceiling zero. Demo mode disables all external queries.

Native development overrides (never commit machine-specific paths):

```dotenv
TRAVEL_MCP_PYTHON=/absolute/path/to/isolated-mcp/python
TRAVEL_MCP_NODE=node
TRAVEL_MCP_MODULES=/absolute/path/to/travel-mcp/node_modules
REDIS_URL=redis://127.0.0.1:6379/0
```

Install with `npm ci --prefix backend/travel-mcp --omit=dev --ignore-scripts`, or use a persistent external runtime directory with the same package/lock files. Do not install dynamically in requests.

## Build, Deploy, Roll Back

1. Run backend tests, frontend tests/build and mocked browser regression `tests/travel-ui.cjs`.
2. Build the current root Dockerfile. It installs locked travel dependencies and Node 22 into a matching Debian Bookworm Python image. Do **not** use the old weather-only layered Dockerfile, which lacks this runtime.
3. After release approval, configure private variables and rebuild/recreate only the isolated staging application using current Compose plus the staging isolation override. Preserve weather variables, previous image references and data volumes.
4. Verify capabilities, unauthenticated flight rejection, free train/hotel search, then one explicitly approved flight request. Verify actual charges separately in the supplier portal; this API does not expose balance.
5. Roll back by setting all three `TRAVEL_*_ENABLED=false` and recreating the API, or restoring its previous image. Keep Redis counters. No database down-migration or data rewrite is needed.
6. Production migration requires separate approval and is not part of this feature.

## Verification

```powershell
python -m pytest backend/tests/test_travel_search.py
npm --prefix frontend test
npm --prefix frontend run build
# Start frontend locally; Playwright must be available on NODE_PATH.
node tests/travel-ui.cjs
```

Browser regression mocks providers and spends no credit. Backend fixtures are synthetic. Do not commit live quotes as reusable price guarantees.

### Local Acceptance (2026-09-16)

- Project bridge returned 20 train seat/price offers, 5 hotel quotes and 5 flight quotes in the live smoke check. These counts are a single run, not coverage guarantees.
- Three potentially billed flight queries were made across connection diagnostics and this integration, within the user's three-query authorization. Actual monetary charges were not checked; make no further live flight call without renewed approval.
- Backend: 215 passed, 4 skipped. Frontend: 25 tests passed; type check and build passed with existing asset/bundle warnings. Mocked Chrome regression passed at 390 and 1280 pixels, including paid consent, quote invalidation, empty/disabled states and contrast.
- Compose configuration validated. Docker image build and real Redis multi-process quota verification remain unverified because the local Docker engine is unavailable. No staging/production deployment or Git push was performed as part of implementation.

## Staging Release (2026-09-16)

- Application source: `d7f99ce`, pushed to `Xcaesar1/JourneyGo` main.
- Image: `journeyops-app:travel-d7f99ce`, successfully built from the root Dockerfile on the ARM64 staging host.
- Release directory: `/opt/tripstar/releases/travel-d7f99ce-20260916`.
- Public site: `https://staging.elonmusk0.asia`, existing Basic Auth preserved.
- Only staging API and Worker were recreated after confirming zero active tasks. Production, PostgreSQL and Redis container IDs/start times remained unchanged.
- Train and hotel queries are enabled on the API. Flight remains disabled with cumulative limit zero: the earlier three-query authorization is exhausted. Worker does not automatically call any travel provider.
- Provider credentials are in `travel.private.env` with mode 0600, outside Git and not copied into the image. Do not print this file or an expanded Compose configuration.
- The original server checkout/environment remain unchanged. Future recreations must include the release override; the old two-file or weather-only command would omit this deployment.

### Recreate Staging

The current staging image is `journeyops-app:brand-4fd35d2` (2026-09-16), containing the simplified result navigation, JourneyGo naming and supplied favicon. Release directory: `/opt/tripstar/releases/brand-4fd35d2-20260916`. It retains the travel release configuration and private environment. No database migration or provider query is required for this UI release.

Acceptance: API/Worker healthy; authenticated public page title is JourneyGo; served favicon SHA-256 matches the supplied JPEG; train/hotel enabled and flight disabled. Browser-only fixture checks passed at 390/1280 pixels with both removed panels absent. Result API responses were mocked for this layout check; no live supplier search or paid model call was made. Source was deployed from the local committed archive; GitHub push was not part of this release.

For the current release, append `-f /opt/tripstar/releases/brand-4fd35d2-20260916/brand.compose.yaml` after the travel override below. Omitting it restores `travel-d7f99ce`, which is also the rollback procedure for the branding release. The branding release's `brand-release-deploy.sh` builds its archived source, checks active tasks, updates only API/Worker, waits for health and automatically restores the travel image on failure. Production, PostgreSQL and Redis container identities/start times were unchanged during deployment.

```bash
cd /opt/tripstar/JourneyOps-staging
docker compose --env-file .env.staging -f docker-compose.yaml -f docker-compose.staging.yaml \
  -f /opt/tripstar/releases/travel-d7f99ce-20260916/travel.release.compose.yaml \
  up -d --no-deps --no-build worker trip-planner
```

Prefer the release's `travel-release-deploy.sh`, which checks active tasks, waits for health, compares protected containers and automatically rolls back on a deployment error.

### Roll Back

```bash
cd /opt/tripstar/JourneyOps-staging
docker compose --env-file .env.staging -f docker-compose.yaml -f docker-compose.staging.yaml \
  -f /opt/tripstar/releases/travel-d7f99ce-20260916/travel.release.rollback.yaml \
  up -d --no-deps --no-build worker trip-planner
```

Both prior application services use `journeyops-app:weather-20260916-r3`. Preserve Redis data and all persistent volumes; do not run migrations or alter ingress.

### Verified After Deployment

- API/Worker healthy, public readiness accessible with Basic Auth, anonymous API requests rejected.
- Real Beijing-to-Xi'an train search returned 20 seat/price offers; Xi'an two-night hotel search returned 5 offers. Repeated requests used cached results and retained fetch timestamps.
- Real Redis test: eight independent concurrent processes shared a three-call ceiling; three reservations succeeded and five were rejected. The counter had no expiry. This used a synthetic account and a mocked supplier, made zero external calls, and removed only its own synthetic Redis keys.
- Direct API flight request without access code rejected; public flight request without paid consent rejected. Flight capabilities/UI disabled. No extra paid queries were made during deployment.
- Browser checked the deployed UI with real train/hotel responses at 390/1280 pixels, source/price semantics and disabled flight controls. Temporary browser-only itinerary data did not modify saved server trips.
- Existing weather smoke passed inside the new Worker with two real forecast days and a deterministic graph, without paid model calls or database writes.
- Full paid-LLM trip generation was not rerun as part of this deployment.
