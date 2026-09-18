# Mobile Travel E2E: 2026-09-18

## Scope

- Target: https://staging.elonmusk0.asia only, real Android Chrome through ADB/CDP.
- Two isolated test trips: 2026-09-20 through 2026-09-24, one adult, CNY 5000 total, business hotel, daily activities 09:00-21:00.
- Exercise real form submission, provider queries, recoverable model failure, modification, review approval, persisted results, six mobile sections, five day panels and map rendering.
- No tickets or rooms booked; no new personal maps created. New personal-map creation/App handoff and image export are not acceptance claims for this run.

## Findings And Changes

- Train queries truncated the earliest 30 services: return candidates ended around 07:13 despite later trains. Query the complete day (`limitedNum=0`); the real route returned 531 outbound and 554 return rows.
- Cheapest/earliest terminal selection chose remote Guangzhou Xintang, leaving almost no local commute allowance. Keep bounded, distinct destination-terminal candidates for each leg, rank verified hotel-terminal distances, and still enforce price/time feasibility. Cache terminal lookups within the planner run.
- Apply the agreed arrival-day rule to both trains and flights: journey duration strictly below 180 minutes and arrival at or before 15:00; at most one sight, only if remaining time/commute limits allow it. Otherwise no arrival-day sights, with an explicit reason.
- Reserve estimated terminal exit time: 30 minutes for train, 60 for flight. Preserve hotel preparation time. No new departure-hour preference was added.
- Sightseeing-date notices now use actual scheduled attraction counts instead of free minutes alone; retain compatibility with older snapshots.
- Align meal classification with validator windows and explicitly represent preparation/rest gaps. Do not invent prices or opening hours.
- Initial flight generation paused with `model_invalid`. A user-triggered retry succeeded using retained supplier results. The original raw output was not retained, so its exact invalid field is unknown. Add safe schema-field/type diagnostics without raw model text or arbitrary field names. Do not claim this eliminates all future malformed model responses.

## Final Saved Results

| Mode | Task | Status | First-day sights | Sights by day | Counted cost |
| --- | --- | --- | --- | --- | --- |
| Train | `task_6557c12b110e4a5ea85e` | completed | 1 | 1, 3, 3, 3, 2 | CNY 2963 |
| Flight | `task_ea3708e702ef4d9993bb` | completed | 0 | 0, 3, 3, 3, 0 | CNY 3610 |

- Train outbound: C7124, Shenzhen to Guangzhou, 06:12-07:35. Return: C7119, Guangzhou to Shenzhen, 22:22-23:42. Both are second-class intercity train services.
- Flight outbound: MU6733, Guangzhou Baiyun to Datong Yungang, 06:40-11:55. Return: MU6734, 12:40-17:45. Use the supplier's total journey duration, not an assumed nonstop duration.
- Both plans retain four hotel nights, five dates, continuous non-overlapping timelines and exact counted-cost arithmetic within CNY 5000.
- Final validation has no critical issues, timeline gaps, unclosed timelines or unreasonable meal-time warnings. `daily_commute_high` and `opening_hours_unverified` remain: local travel is distance-based estimation, and attraction hours/ticket requirements are not certified. These are not fully verified executable itineraries.
- Real mobile checks: six section buttons, five expandable day panels, AMap canvas/markers, no captured page errors and no document horizontal overflow at 363 CSS px. UI checks were performed during the release sequence; final data assertions use the completed snapshots.
- Supplier/source display limitations observed: a Guangzhou POI address contains repeated street text; some hotel/weather labels remain in provider English. Not corrected as authoritative source facts in this patch.

## Verification

- 108 targeted backend tests: one-click planning, place selection, query ledger and travel search.
- 60 frontend tests and production build passed. Existing legacy asset-path and bundle-size warnings remain.
- Ruff passed for changed backend modules/tests.
- Ignored local evidence: `artifacts/mobile-e2e-{train,flight}.json`, mobile screenshots, `mobile-e2e.cjs`, `mobile-verify.cjs`. Do not commit private supplier results, browser credentials or personal-map tokens.
- Flight counter started at 4, became 6 after the two authorized real leg queries, and stayed 6 across recovery/replanning. Limit remains 10. No automatic quota increase/reset.

## Deployment

- Code release: `a8ac897`; API `journeyops-app:cities-api-a8ac897`, worker `journeyops-app:cities-worker-a8ac897`.
- Release directory: `/opt/tripstar/releases/mobile-a8ac897-20260918`.
- Frontend rule notices shipped in `fbbf749`; subsequent backend-only layers retain that frontend.
- Both containers healthy. Each rollout checked zero active tasks, retained Compose overrides, and compared task/review/version/query hashes and the paid counter before/after deployment. Intended test submissions/reviews happened outside those comparison windows.
- Production, demo and staging database/Redis container identities and start times were unchanged. No database migration.
- Roll back application images only using this release's `previous-compose-files.txt`, after the active-task check. Preserve feature flags, cumulative quota, database volumes and saved test versions.
