# Mainland Flight City Registry

## Source And Scope

- Source: China Southern's public booking-city data,
  https://www.csair.com/comp/cityDate.json (referenced by its official `/comp/uiLib.js`).
- Provider contract: https://github.com/variflight/variflight-mcp .
  `getFlightPriceByCities` takes city codes, not arbitrary airport identifiers.
- Snapshot: `backend/app/domain/data/flight_cities.json`; retain retrieval date,
  original source SHA-256, city codes and associated airport names/codes.
- The September 18 snapshot includes 254 mainland aviation city/place entries.
  This is a nationwide directory, not proof that every place has scheduled flights
  or that the provider sells every route/date. Do not claim universal live acceptance.
- Exclude international/regional entries, ground-only stations/terminals and the
  source's inconsistent Da'an-to-Liangping association. Do not guess nearby airports.
- Preserve metropolitan identifiers such as BJS, SHA, CTU and SIA. Five new-airport
  entries have reviewed overrides from the associated airport fields rather than
  the airline's internal city/rail identifiers. Provider acceptance of every rare
  code has not been live-tested; do not spend quota doing bulk validation.
- Ambiguous Zunyi requires explicitly choosing 新舟 or 茅台. City aliases are explicit,
  reviewed data, not fuzzy matching. Exact names take precedence over removing 市.
- Mainland-only planning constraints are unchanged. Cities without a matched
  aviation entry are not silently substituted, and no paid request is dispatched.

## Integration

- `domain/flight_cities.py` loads the local snapshot; no runtime source/network dependency.
- One-click preflight and query construction share `flight_city_code`.
- `/api/v2/travel/capabilities` exposes the same `flight.city_codes` mapping for
  the quote form. Do not add a separate frontend whitelist.
- Keep existing paid consent, quota ceiling, credential counter and durable quote reuse.

## Refresh And Verification

1. Run `python backend/scripts/update_flight_cities.py` to validate the public source.
2. Run with `--write` to generate a candidate snapshot; review the diff before committing.
3. Investigate deletions, metropolitan-code changes and new internal identifiers.
   Do not auto-publish an unreviewed upstream update.
4. Run `pytest backend/tests/test_flight_cities.py backend/tests/test_one_click_travel.py backend/tests/test_travel_search.py`.
5. Build the frontend and run `node tests/flight-city-ui.cjs` with the project dev server.
   Browser API responses are mocked. `--live` additionally verifies staging's public
   mapping and uses deployed assets, still without making paid requests.
6. Deploy API and worker together with the snapshot and resolver. Preserve staging
   flight enablement and cumulative quota; do not change production or reset counters.
