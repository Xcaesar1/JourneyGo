# One-click travel implementation status

## Status (2026-09-17)

Partial implementation only. The approved complete-trip workflow is NOT enabled
and has NOT been connected to the homepage or JourneyGraph. No database changes,
new public API, deployment, booking or paid flight request were performed.

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

Obtain authoritative documentation or a verified read-only response for the CN
endpoint that specifies the whole-stay rate for the requested one-room occupancy,
currency, sales availability and any supplied tax/fee information. Unknown taxes
may remain explicitly unknown; an unknown price basis cannot become a quote.
Record the contract and add a sanitized synthetic fixture before accepting rates.

## Remaining Approved Work

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

Foundation verification on 2026-09-17: backend suite passed with 255 tests and
4 skips; changed Python files passed Ruff and `git diff --check`. Frontend and
mobile/desktop acceptance were not run for this backend-only foundation. The
complete-trip acceptance matrix remains unimplemented and unverified.

Run `python -m pytest backend/tests/test_hotel_detail.py backend/tests/test_travel_search.py`.
Run `python -m pytest backend/tests` and the existing frontend tests/build before
claiming the complete feature is ready. Supplier tests must remain mocked.

This foundation has no migration or active graph/UI changes. Reverting its code
does not affect existing versions, quotes, database contents or paid-call counters.
