# Planning Pause Recovery

## Contract
- Select attractions separately from dining interests. General attraction discovery performs at most three distinct keyword queries; explicit must-visit lookup remains separate. Deduplicate by POI ID and retain avoid/must-visit constraints.
- Small candidate pools are advisory when the deterministic scheduler can produce a feasible trip. Empty pools, missing required sights, invalid coordinates, budget and time conflicts still stop planning.
- Selection contract v3 supplies `activity_windows` after choosing feasible transport and hotel. Windows subtract arrival transfer/check-in and return transfer/buffer; transfer dates are not assumed to be full sightseeing days.
- `requirement_issues` reference an actual request field and exact quote. Unsupported invented requirements are ignored. Ordinary preferences become notices; explicit constraints can block. Existing `unmet_requirements` remains readable for old responses but cannot invent requirements when the user supplied none.
- Structured accessibility needs and explicit allergy/wheelchair needs in free text remain unverified without supporting facility/safety evidence; absence of model issues does not certify them. This is not a full natural-language medical/dietary classifier.
- `travel_summary.activity_windows` and `planning_notices` are additive. The summary shows limited sightseeing time and advisory notices without expanding details. Old plans without these fields retain their existing display.

## Resume Without Supplier Refresh
- Continuing legacy `unmet_requirements` (including `provider=null`) or new `requirement_confirmation` increments only the model revision by default.
- Model-only recovery tries already-cached attraction queries, including the old mixed-interest key. Missing cached keys do not dispatch new supplier requests. Existing ledger guards still apply to transport, hotels and maps.
- New attraction searches during initial planning are bounded. An explicit source refresh remains necessary if recovery cannot produce a usable plan from cached places.
- Recovery is user-triggered. Do not automatically resume, rewrite or approve the real paused task. No deployment/commit is included in this local fix.

## Regression Coverage
- Three-day Shenzhen/Shanghai fixture with two nearby sights, evening arrival and morning return; unrequested accessibility/dietary warnings do not pause it.
- Bounded fallback, POI deduplication, empty pools and reuse-only legacy-key recovery.
- Actual accessibility/allergy requirements, quoted mandatory requests, ordinary preferences and negated safety needs.
- Continue endpoint preserves provider revisions and rejects duplicate continuation.
- Existing hard timing, budget, must-visit and invented-POI checks remain enabled.

## Local Verification (2026-09-18)
- Backend: 358 passed, 4 skipped; frontend: 47 passed. Production build and changed-file Ruff checks passed; existing asset-path/chunk-size warnings remain.
- Mocked Chrome at 360/390/768/1440 px: notices and main sightseeing dates visible, no horizontal document overflow, zero POST requests.
- Screenshots: `artifacts/planning-notice-{width}.png`. No real model/provider request, task continuation, review, commit or deployment was performed.
