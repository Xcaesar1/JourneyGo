# City landmarks and repeated experiences

## Contract

- Complete landmark, must-see and interest query families before reducing candidates. Reuse existing query ledger records. Keep the existing optional Ctrip supplementation configuration.
- Rank explicit requirements before curated landmarks, interest preferences and ordinary candidates. Preserve model order within each priority tier; use distance for feasibility and route optimization.
- Default homepage selections populate `preferred_attractions`. Explicit choices populate `must_visit`; deselections populate `excluded_attractions` and apply to the whole curated experience group.
- Resolve duplicate explicit requirements by asking which concrete place to keep. Never construct a synthetic combined attraction.
- Identity rules live in `backend/app/domain/landmarks.py`; each rule includes an official source. They are identity/experience rules, not a popularity ranking. Every itinerary location still requires an AMap POI.
- Seed landmarks: Oriental Pearl, Jade Dragon Snow Mountain, Yellow Crane Tower, Yungang Grottoes, Canton Tower, Palace Museum, Badaling Great Wall. Mutianyu retains its own identity/source but shares the Great Wall experience group.
- Datong old city/wall/south-wall use one concrete POI. Huayan and Shanhua temples are not members of that group.

## Scheduling and evidence

- Ordinary candidates retain the compatible 90-minute fallback. Curated landmarks carry ordinary/half-day/full-day estimates. All current visit durations are explicitly planning estimates, not official requirements.
- Determine landmark duration before hotel ranking. Half/full-day and distant core sights use a non-transfer day, including separately budgeted outward transit, visit, 60-minute meal/rest and return transit.
- Dedicated days require AMap public-transit evidence in both directions. Reject taxi/rail-only substitutions and excessive walking; do not substitute a driving estimate. Future service times remain unverified and require pre-departure confirmation.
- Preserve the first-day rule: outbound duration below 180 minutes, arrival at or before 15:00, at most one attraction.
- Missing landmark identity or infeasible core sightseeing pauses with a specific cause and explicit recovery actions. Dates, budget and transport are never silently changed.
- Persist `landmark_coverage`, `deduplicated_places`, source and duration basis in the travel summary. Old optional-field-free data still renders.
- Opening hours, reservations, ticket prices and unquoted meal costs remain explicitly unverified. Do not treat a successful draft as a booking.

## Verification and release

- Regression suite: `backend/tests/test_landmark_planning.py`, discovery/recovery/quote-ledger tests and frontend preference/recovery tests.
- Local full backend suite, frontend tests and build are required before deployment.
- Stage only at `https://staging.elonmusk0.asia/`. Preserve production containers, database state across deployment, map identities and the flight cumulative limit/counter.
- Reuse existing Shenzhen-Guangzhou and Guangzhou-Datong five-day trips dated 2026-09-20 through 2026-09-24. Refresh AMap evidence explicitly; never refresh flight quotes or increase their quota.
- Live staging verification is pending at the time of this implementation commit; append actual results after testing.
