# Mobile E2E: 2026-09-19

## Result

- Shenzhen to Wuhan: completed and approved, real G1040/G1042 round trip, five days and four nights. Known quotes plus estimates total CNY 2802, not an all-inclusive booking price.
- Guangzhou to Lijiang: awaiting input, not a completed itinerary. Jade Dragon Snow Mountain has no returned public-transit route from the attraction to any of three candidate hotels. Do not present this case as successful.
- Datong regression: completed and approved as version 3 using retained flight quotes. Yungang occupies one dedicated day; independent temples remain separate.

## Conditions And Evidence

- Physical AAK_AN00 Android phone, Chrome over ADB/CDP, 363 CSS-pixel viewport. These are actual staging screenshots, not mockups or desktop mobile emulation.
- Both requested routes: 2026-09-20 to 2026-09-24, one adult, CNY 5000, business-tier hotel, no booking.
- Completed Wuhan and Datong cases: six sections inspected, all five daily panels expanded, one map canvas rendered, no captured page errors or horizontal overflow. Wuhan touch carousel gesture changed the active card.
- Wuhan G1040: Shenzhen North to Hankou, 10:23 to 15:42. Return G1042: 15:04 to 20:32. The first day has no attraction. Yellow Crane Tower receives 120 estimated minutes on September 21.
- Datong Yungang day: outward bus 101 minutes, sightseeing 180 minutes, meal/rest 60 minutes, return bus 107 minutes. Flight query records remain exactly two.
- Lijiang homepage: main snow-mountain candidate is first, estimated duration 360 minutes; known internal components no longer consume separate default recommendations.
- Lijiang dated queries: September 21, 22 and 23, three hotels. Each has an outbound route but zero return routes at the calculated departure time. Two additional diagnostic probes at 16:00 and 17:18 on September 21 also returned zero routes. Empty results are not evidence that no physical bus service exists.
- Lijiang recovery action for changing preferences was clicked: explanatory hint and focus/scroll appeared, with zero POST requests. The continue action actually resumed the same task after deployment and returned the same specific blocker.
- No attraction was silently skipped, no charter substituted, and no personal AMap was created. Public embedded map display is not personal-map creation.

## Code And Release

- Initial live checks used `589339a`, including the earlier dedicated-day validation fix `c43c52e`.
- Found and fixed missing departure date/time in landmark transit requests: `0f3d67c`. Outbound uses the planned day start; return uses arrival plus visit plus meal/rest. Cache identities now include both date and time.
- API semantics: [AMap public-transit request documentation](https://lbs.amap.com/api/webservice/guide/api/direction).
- Final backend: 713 passed, 4 infrastructure integration tests skipped; Ruff passed. Frontend: 63 passed; production build passed with existing asset/chunk warnings.
- Staging API/worker use `cities-api-0f3d67c` / `cities-worker-0f3d67c`, healthy. Release: `/opt/tripstar/releases/landmarks-0f3d67c-20260919`.
- Release script completed with active task count zero and matching before/after quota, business-data hashes and protected production/demo/database container identities.
- Flight cumulative limit remains 10. Usage moved from 6 to 8 only for the new Lijiang round trip; recovery reused those two successful records.

## Files And Privacy

- Each route directory contains a sanitized `verification.json` and selected page-only screenshots. No credentials, cookies, browser storage, or full supplier responses are included.
- Wuhan screenshot sequence: form, landmark, saved overview, transport/hotel, landmark day, budget and map.
- The `form-route.png` and `form-preferences.png` views re-enter the same retained inputs in a fresh phone tab without submitting. Initial long-element captures were malformed on Android; raw originals are retained privately, not used as submission proof. Submission conditions and identifiers are preserved separately in `verification.json`.
- Lijiang sequence: form, landmark and actual blocked state. There is no final Lijiang overview, budget or completed timeline to show.
- Full five-day screenshots and raw supplier evidence remain in ignored `artifacts/mobile-e2e-*/` directories.
- A 40-second physical-phone screen recording is retained at `artifacts/mobile-e2e-shenzhen-wuhan/phone-screenrecord.mp4`. It is not published: video-frame privacy review has not been completed. The separate later touch-carousel check passed; the recording must not be described as proof of that later check.
- Opening hours, tickets, reservations, some meals, hotel taxes and unprovided flight taxes remain unverified. Bus times are estimates, not guaranteed future departures.

## Lijiang Next Step

The user authorized charter evaluation, not booking or silently replacing the current request. See [charter assessment](charter-assessment.md). Keep task `task_0954c6f772aa4cc6b128`; do not submit a new flight task or refresh flight queries. The current product has no verified charter-quote input contract, so external research is not a completed in-app charter itinerary.
