# One-click travel implementation status

> 命名说明：本文中的名称已统一为 JourneyGo，历史服务器标识请查阅提交 `def71ad` 中的原文件；本次未迁移线上环境。升级前阅读仓库 `docs/BRANDING_MIGRATION.md`。

## Nationwide City Coverage (2026-09-18)

- The seven-city whitelist is superseded by the 254-entry, versioned mainland
  aviation registry and reviewed aliases. Shenzhen-Wuhan now passes both-leg
  code mapping and mocked planning tests; exact city names such as 芒市 are preserved.
- Quote UI receives its mapping from the same backend registry. No runtime scrape,
  guessed neighboring airport, extra paid query, quota reset or production change.
- Directory coverage does not guarantee direct service or sale inventory for every
  route/date. Whole-country paid acceptance was not performed. See
  `FLIGHT_CITY_REGISTRY.md` and the latest `DEPLOYMENT.md` section.

## Flight Enablement (2026-09-18)

- Staging API and worker flights are enabled with the explicitly approved
  cumulative ceiling of 10 calls. Two real round-trip probe calls succeeded;
  remaining allowance was 8 at release verification. Production remains untouched.
- Supported planning city mappings now include Kunming and Lijiang in addition
  to Beijing, Shanghai, Guangzhou, Hefei and Xi'an. Unsupported cities still fail
  before provider dispatch; do not infer that all domestic cities are mapped.
- KMG-LJG city-pair reference:
  https://www.caac.gov.cn/XXGK/XXGK/ZFGW/201601/P020160122452510922835.pdf
- Provider tool contract:
  https://github.com/variflight/variflight-mcp#get-flight-prices-by-cities
- Real quotes passed normalization and planning eligibility. Full planner tests
  use mocked suppliers/model and verify both directions and quote reuse. A real
  whole-trip flight itinerary was not generated or substituted into an existing task.
- See the staging flight section in `DEPLOYMENT.md` for images, proof and rollback.
  Historical disabled-flight notes below describe earlier deployment states.

## C-prefix Train Correction (2026-09-18)

- Accept G/D/C train numbers with available second-class seats, valid prices and
  same-day arrival. Continue rejecting unsupported trains, standing tickets,
  insufficient seats, missing prices and date mismatches.
- Kunming-Lijiang investigation found 11 valid C-prefix records in the saved
  outbound result, previously discarded by a G/D-only downstream filter.
- Preserve supplier query arguments and ledger identities so saved successful
  results remain reusable; do not clear caches or automatically resume tasks.
- Transport failure text identifies the leg/date/route and distinguishes an empty
  supplier response from returned offers that fail eligibility checks. Neither
  is described as proof that no direct train operates.

## Status (2026-09-17)

### Approved staging release

- The user approved deployment before live functional acceptance. Staging now
  runs `journeygo-app:one-click-f35652d`, including integrated workflow commit
  `d7fe4a2` and homepage language commit `f35652d`.
- Homepage language selection is Chinese/English only. Saved Japanese/Korean
  selections fall back to Chinese on entering the homepage; locale packs remain
  for historical result compatibility.
- `ONE_CLICK_TRAVEL_ENABLED=true` on API and Worker; train/hotel enabled,
  paid flights disabled with the existing zero limit. Production is unchanged.
- PostgreSQL migration `20260917_07` ran successfully after a verified custom
  dump backup. API/Worker health, private HTTPS authentication, readiness and
  feature capabilities passed. PostgreSQL/Redis containers were not restarted.
- Local frontend suite: 31 passed; build passed with existing asset/chunk
  warnings. Chinese/English phone/desktop homepage and mocked planning tests
  passed, including saved Japanese/Korean fallback and two-option dropdown.
- Deployed-asset browser checks also passed via an SSH loopback tunnel:
  homepage, one-click mock flow and legacy result/export compatibility. These
  checks mock all API/provider responses and are not live planning acceptance.
- Real model/supplier end-to-end acceptance is still pending. No paid flight
  request or additional quota was authorized or consumed by deployment checks.
- Release and rollback details: `docs/DEPLOYMENT.md`, one-click staging release.

### Integrated implementation, local mocked acceptance

The remaining application workflow is now connected behind
`ONE_CLICK_TRAVEL_ENABLED=false`. The earlier foundation-only status below is
historical. At that implementation checkpoint, no staging/production deployment
or paid provider call had been made; see the later release above.

- JourneyGraph runs verified round-trip transport, bounded hotel search/detail,
  verified POI discovery, structured model selection and deterministic scheduling.
  The model selects only existing POI IDs; unmet hard requirements pause the task.
- New mode supports one mainland destination, 1-2 adults, one room and 2-29 days.
  Train dates must both be within the inclusive 15-day sale window. Flight dates
  and city codes are validated before dispatch; supported city mappings are
  Beijing, Shanghai, Guangzhou, Hefei and Xi'an. Never substitute airport codes
  for city codes. Xi'an `SIA` is corroborated by the CAAC city-pair reference:
  https://www.caac.gov.cn/PHONE/XXGK_17/XXGK/ZFGW/201601/P020160122452786310808.pdf
  This is not a live paid-flight integration acceptance.
- PostgreSQL migration `20260917_07` adds query intents/results/authorization and
  task `pending_input`. Intent commits precede dispatch. Ambiguous dispatches
  never auto-resend. Redis paid-call counters are not refunded or reset.
- `awaiting_input` is distinct from final approval. Continue is access-protected;
  saved requests and query snapshots support refresh/restart recovery. Explicit
  refresh gets a new persisted intent identity; unrelated flight results remain.
- Hotel tier reaches supplier filters and local ranking. Search is bounded to
  10 candidates and 3 details. Reference prices are estimated once per room/stay;
  list fallback requires eligible room evidence. No booking/locking tools exist.
- Results preserve POI IDs, quote timestamps, source URLs and integer-cent cost
  items through adapters/versions. Reference hotel total, daily dining allowance
  (including travel-day meals) and local transport are estimates. Tickets and
  unavailable taxes remain excluded/unknown. Opening hours remain unverified
  unless separately checked; the generated visit is not an opening guarantee.
- Homepage and result cards support four UI languages, flight consent reset,
  simplified inputs, return date, pause recovery, navigation and quote proposals.
  Quote changes enter existing review/version flow; confirmed requests and active
  versions are committed together. Legacy manual queries and saved plans remain.

Local checks include fixed Shanghai-Xi'an September 20-24 fixtures, four hotel
nights, one/two adults, late arrival, early return, no seats/rooms/prices, POI
failure, over-budget, model-invented IDs, unmet requirements, bounded hotel detail,
round-trip flight reuse, interrupted dispatch, duplicate delivery, protected
continue and atomic version activation. All external/model responses are mocked.

PostgreSQL migration SQL generation passed. **Live PostgreSQL/Celery integration
is not verified on this host:** Docker's Linux engine is unavailable. The existing
four opt-in integration tests require their database/runtime environment. Keep
the feature OFF by default. The subsequent user-approved staging release above
enables it for live acceptance after successful isolated migration.
Real paid flight acceptance and any additional quota require separate approval.

Final local verification for the integrated change: **293 backend tests passed,
4 skipped; 31 frontend tests passed; production build, Ruff and diff whitespace
checks passed.** Build retains the pre-existing optional asset/chunk warnings.
`tests/one-click-ui.cjs` passed in four locales at 390/1280px; legacy
`tests/travel-ui.cjs` passed including export. No live model/supplier call occurred.

### Latest decision: reference estimates accepted

The user explicitly accepted reference prices for accommodation budgeting.
This supersedes the earlier whole-stay-price blocker below, not the other
transport, inventory, occupancy, budget or recovery requirements.

- Detail `averagePrice` is treated as a nightly reference by product decision,
  not as a newly verified supplier contract. Multiply by nights once per room.
- List `lowestPrice` remains a first-night reference. Its stay estimate assumes
  the same nightly rate and must be displayed as estimated, never as a quote.
- Unknown taxes remain unknown. Missing prices never become zero. No booking or
  lock is performed. Room evidence and occupancy checks remain required to claim
  a specific room recommendation; a list price alone cannot prove room stock.
- Added `estimated_stay_total` distinct from the unverified `stay_total`.
  Manual search returns `first_night_reference` and displays the estimated total.
- Hotel cache namespace moves to v2; train/flight cache and paid counts are unchanged.
- Historical findings below describe why this explicit product decision was needed.

Reference-pricing validation: 263 backend tests passed, 4 skipped; 31 frontend
tests passed; frontend production build passed with existing asset/chunk warnings.
Mocked browser regression passed at 390px and 1280px, including reference-total
display, flight consent and export. No live supplier calls or deployment occurred.

Historical foundation status: the workflow was not yet connected at this point.
The integrated implementation is described above; it remains disabled by default.

The first prerequisite uncovered a supplier contract gap. Do not present the
existing estimated planner as the approved verified-transport-and-hotel workflow.

## Verified prerequisite

Read-only inspection used the existing staging hotel credential without printing
or persisting it. The online endpoint exposes these tools:

- `searchHotels`
- `getHotelDetail`
- `getHotelSearchTags`

All three report no output JSON schema. The online input schema differs from the
public Python implementation: detail does not declare `localeParam`; hotelTags
accepts `maxPricePerNight`, `preferredBrands`, `requiredTags`, not `preferredTags`.

One Xi'an search for one adult and four nights returned three hotel candidates.
The first candidate's detail returned 13 room rate plans. The sampled first room
contains `ratePlanId`, `roomName`, `averagePrice`, `currency`, `isOnRequest`,
`roomInfo.maxOccupancy`, meal and cancellation fields. It does not contain an
explicit stay total or included/excluded tax fields. Only structural field types
were printed; no actual quotes or credentials were stored in source control.

This observation does not prove that every hotel lacks totals. It establishes
that the observed response cannot safely satisfy the required whole-stay quote
contract. There is no verified definition of `averagePrice` for this endpoint.
Do not infer its basis, multiply it by nights, or substitute the search-list
`lowestPrice`. Do not invoke `hotelPriceConfirm` or OAuth/booking tools to work
around this restriction; they are outside the approved read-only scope.

Sources inspected:

- https://raw.githubusercontent.com/RollingGo-AI/rollinggo-hotel-mcp/main/rollinggo_hotel_mcp/tools/hotel_detail.py
- https://raw.githubusercontent.com/RollingGo-AI/rollinggo-hotel-mcp/main/rollinggo_hotel_mcp/models.py
- https://github.com/RollingGo-AI/RollingGo-hotel-MCP-CN

The Python source passes through the upstream response without specifying its
fields. The CN README also directs clients to the actual response. Global/CLI
examples with different fields are not evidence of the live CN API contract.

## Implemented Foundation

- Extend the isolated bridge with a strict per-provider read-only tool allowlist.
- Validate the tool before opening a connection or spawning a process.
- Preserve old train/flight/search payloads and existing quota/cache behaviour.
- Add a hotel detail adapter for explicit dates, one room, and one/two adults.
- Match response hotel/date scope and filter rooms by known capacity and
  `isOnRequest=false`; these are candidates, not booked rooms or price guarantees.
- Retain the supplier's average as Decimal evidence, never as a whole-stay quote.
- Return a blocked result with unknown total/taxes, without retrying failures or
  leaking provider exception text.
- Keep the adapter separate from legacy estimates until the new graph is ready.

## Unblocking Requirement

### Follow-up verification (2026-09-17)

The official website's rendered documentation showed a load failure. Its public
documentation API, discovered from the site's own JavaScript, successfully served
the current tool reference:

- https://rollinggo.store/api/public/docs/spaces/mcp-docs/pages/mcp-tool-reference
- https://rollinggo.store/api/public/docs/spaces/faq/pages/faq
- https://raw.githubusercontent.com/RollingGo-AI/rollinggo-hotel-skill-cn/main/skills/rollinggo-hotel-booking/references/cli-params.md

Confirmed facts:

- The current tool reference explicitly describes `searchHotels.price` as a
  first-night estimated minimum display price, NOT a complete-stay total.
- Its API-key `getHotelDetail` example matches the observed `averagePrice` shape,
  but still does not define its billing basis, rounding or included taxes.
- The official CLI parameter reference defines `averagePrice` as nightly average
  in the price-confirm response, while its detail response describes different
  fields (`totalPrice`, `totalSalesRate`). Do not transfer that definition to the
  current API-key detail response without confirmation.
- A fresh read-only `tools/list` description promises room/price/tax detail but
  provides no field-level billing definition or output schema.
- The FAQ states search and detail prices are reference prices; final booking
  prices require the separate locking tool. Planning does not require a locked
  final price, but it does require a known quote basis and explicit unknown fees.

Correction required in the existing manual search: `travel_search.normalize`
currently marks hotel list `lowestPrice` as `stay_total` and labels it a multi-night
total. This is contradicted by the official reference. Correct the response basis,
frontend display/types, fixtures and any cache interpretation before reuse in the
new planner. This follow-up only verifies the contract; it has not changed that
runtime behaviour or deployed a correction.

Supplier clarification to request (not sent): For API-key `getHotelDetail`, one
room, one/two adults, four nights: is `averagePrice` the arithmetic nightly average
over the entire requested stay? Is it rounded, and to what precision? Which taxes
and mandatory fees are included/excluded? Can this read-only interface return the
unrounded whole-stay total or daily price breakdown without price locking or an
order? Official support: contact@rollinggo.ai. Never include credentials.

Obtain authoritative documentation or a verified read-only response for the CN
endpoint that specifies the whole-stay rate for the requested one-room occupancy,
currency, sales availability and any supplied tax/fee information. Unknown taxes
may remain explicitly unknown; an unknown price basis cannot become a quote.
Record the contract and add a sanitized synthetic fixture before accepting rates.

## Original Implementation Checklist (Application Work Now Integrated)

- Add one-click request mode, independent disabled-by-default feature flag,
  domestic round-trip validation and both-leg train-window preflight.
- Add PostgreSQL intent/result ledger with uniqueness, query scope and flight
  consent, preserving Redis's non-refundable cumulative paid-call ceiling.
- Add `awaiting_input`, protected resume, partial invalidation and restart
  recovery; keep final itinerary approval separate.
- Integrate real train/flight selection and hotel search/detail into JourneyGraph;
  search at most 10 hotels and inspect at most 3, with actual tier filtering.
- Add verified restaurant/hotel/terminal POI matching, navigation metadata and
  actual departure/arrival/transfer buffers to deterministic validation.
- Add integer-cent/Decimal cost ledger and immutable result/version/export fields.
- Simplify homepage in four languages, add flight consent, return-date display,
  progress/pause recovery and transport/hotel result cards.
- Run the approved Shanghai-Xi'an five-day mocked acceptance matrix, backend and
  frontend suites/build, mobile/desktop flow and old-plan compatibility tests.
- Request approval before staging publication. No production work or new real
  paid flight acceptance is authorized.

## Validation and Rollback

Historical foundation verification on 2026-09-17: backend suite passed with 255 tests and
4 skips; changed Python files passed Ruff and `git diff --check`. Frontend and
mobile/desktop acceptance were not run for this backend-only foundation. The
complete-trip acceptance matrix was still unimplemented at that earlier point.

Run `python -m pytest backend/tests/test_hotel_detail.py backend/tests/test_travel_search.py`.
Run `python -m pytest backend/tests` and the existing frontend tests/build before
claiming the complete feature is ready. Supplier tests must remain mocked.

Rollback the new workflow with `ONE_CLICK_TRAVEL_ENABLED=false` on API and Worker.
Keep migration `20260917_07`, query records and paid counters. Its destructive
downgrade is intentionally refused. Do not drop the table or stamp back the
migration revision; re-enable only after checking retained intents and approvals.
