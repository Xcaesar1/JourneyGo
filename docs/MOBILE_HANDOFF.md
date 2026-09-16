# Mobile Debugging Handoff

Updated: 2026-09-16. Read AGENTS.md and verify current state before acting.

## Continuation verification (2026-09-16)

- Real AAK-AN00 reconnected successfully at 363x705 CSS pixels, DPR 3.5.
- Saved Xi'an coordinates are valid. The immediate NaN root cause was a zero-height
  map container (percentage height inside auto-height parents), not corrupt trip data.
- A definite map height restores actual AMap tiles and both markers. Leaving the map
  also requires destroying its instance; otherwise the hidden zero-width container
  triggers Pixel(NaN). Generation checks discard obsolete async initialization/routes.
- Local production assets were temporarily served to the real staging phone tab through
  CDP request interception. API, historical trip and AMap SDK remained real/unmocked.
- Native CDP touch events passed Overview, Map, Daily Itinerary, Knowledge Graph,
  Map again and Overview; two map markers, no page errors after lifecycle fix.
- `npm test`: 23 passed. `npm run build`: passed (existing legacy-asset/chunk warnings).
  `artifacts/navigation-smoke.cjs`: passed supplemental desktop fixture regression.
- Changes remain frontend-only; no API/schema/history changes.
- `artifacts/phone-verify.cjs`: LOCAL_BUILD=1 checks local dist on physical phone;
  omit LOCAL_BUILD to validate deployed staging assets. It never mocks API or AMap.

## Published outcome (supersedes the original handoff below)

- Fix commit `f62e7bd`; staging image `journeyops-app:mobile-f62e7bd`.
- Published to staging only via `/opt/tripstar/releases/mobile-20260916/deploy.sh`.
  Previous image `journeyops-app:branding-732d191` retained; private env backup in
  the release directory. Only IMAGE_TAG changed. No migration or worker restart.
- Production and worker container ID/image/restart/start-time snapshots matched.
- Public valid TLS; homepage, temporary AMap page and readiness return anonymous
  401 / authenticated 200. JS/CSS bytes match local dist exactly.
- Deployed assets passed the same real-phone touch panel cycle, including returning
  to map. Both markers rendered; no page errors. Language dropdown and settings
  open/close passed by touch, without saving settings. Card/date bounds do not overlap.
- Temporary `/amap-test.html` was loaded on phone and its link was tapped using native
  CDP touch. Android foreground changed to com.autonavi.minimap. Expected two Xi'an
  places were NOT verified; observed app later showed a place-editing screen. No save,
  purchase, route start or account change was performed by this task. Do not claim
  personal-map import, token lifetime, or in-app walking/transit routing passed.
- The native app screen can contain private current-location information; its ignored
  artifact screenshots must not be committed or shared. Do not inspect unrelated data.
- Existing trip feasibility issues remain unchanged. Build still warns about legacy
  assets and large chunks. Desktop fixture regression remains supplemental only.

## Original handoff snapshot (historical, before continuation)

## Objective and authorization

- Fix JourneyOps on the user's real Android phone, then validate and deploy staging only.
- User approved staging deployment of mobile layout fixes, walking/transit navigation, and a temporary AMap test page.
- Do not change production, historical trip data, database schema, DNS, or access controls.
- User prefers walking and public transit; driving is out of scope.
- Emulator installation was cancelled. Command-line tools archive was deleted; no emulator/system image installed. Do not resume it.
- Current user request: hand off to a new conversation, then continue fixing and validating.

## Workspace

- Work directly in Q:\VPS\JourneyOps, branch staging. Do not create a worktree or discard uncommitted work.
- HEAD 3796c84 (protected staging HTTPS documentation).
- Previous commit 2e03ece adds walking/transit navigation. Base 732d191 contains branding.
- Uncommitted mobile work: frontend/src/views/Result.vue, frontend/src/components/NavBar.vue, frontend/src/components/OverviewAttractionCard.vue, frontend/package.json, frontend/src/views/Result.mobile-layout.test.mjs, docs/CHANGELOG_FROM_UPSTREAM.md.
- Preserve these edits, review their diff, and finish them rather than recreating them.
- Existing fixes include mobile section-button grid, wrapping action buttons, single-column attraction cards, smaller dark mobile overview cards, and navbar width correction.
- No backend/API/schema changes have been made for this mobile work.
- Follow project rules for separate feature commits; do not push unless requested.

## Real phone connection (verified)

- HONOR WIN RT, AAK-AN00; Android 16; Chrome 149.0.7827.115.
- Physical resolution 1272x2800, density 560, devicePixelRatio 3.5; web viewport approximately 363x705 CSS pixels.
- Q:\Android\platform-tools\adb.exe is official Platform Tools 37.0.1.
- USB authorization was accepted by user. `adb devices -l` returned state device, not unauthorized.
- Forward for Chrome: `adb forward tcp:19222 localabstract:chrome_devtools_remote`.
- CDP endpoint http://127.0.0.1:19222; connect using Playwright chromium.connectOverCDP.
- Only inspect the JourneyOps tab; do not inspect unrelated tabs or phone data.
- Phone tab is https://staging.elonmusk0.asia/result?plan_id=task_cce34c13907342d9b6c6.
- Recheck connection first. User keeps USB connected and phone unlocked; may need another authorization after reconnect.
- No backup, sync, rooting, flashing, or mobile app installation was performed.
- HonorSuite 11.0.0.736 official signature was valid. Its silent installer ignored /D=Q:\Android\HonorSuite and installed at C:\Program Files (x86)\HonorSuite. User was informed. Do not claim Q installation or relocate/remove it without appropriate confirmation. Driver repair was not independently proven; connection succeeded after user accepted USB prompt.

## Verified findings on deployed staging (before fixes)

1. Navbar language/settings/start buttons are outside viewport: controls extend to x approximately 524 on a 363-wide viewport.
2. Result menu width approximately 813 inside a 313-wide region; map/days/graph entries are clipped and action controls overlap.
3. Overview carousel/card overflows and date metadata is overlapped; text contrast is poor in current screenshot.
4. Map is NOT merely hidden by navigation: programmatically selecting its inaccessible menu entry produced pageerror `Invalid Object: LngLat(NaN, NaN)` and `Failed to load map`. Trace exact coordinate source before fixing. Do not rewrite stored trips.
5. Daily itinerary content renders when selected via diagnostic click. Knowledge graph also renders nodes/edges. They are not missing data; normal entry access is broken.
6. Existing Xi'an trip has feasibility critical errors (40-hour estimated inbound transit and out-of-date-day activities). This is existing plan data, not a CSS fix. Do not silently change it.

Inspection used programmatic menu clicks only to diagnose panels blocked by layout. This does NOT count as successful user-tap navigation. Real tap verification remains required.

## Local diagnostics and test state

- artifacts/ is ignored by Git. Diagnostic script artifacts/phone-inspect.cjs connects to real phone, reads layout and captures screenshots.
- OPEN_TRIP=1 opens the saved Xi'an trip from homepage. AUDIT_PANELS=1 diagnostically switches map/days/graph and reports errors, then restores Overview.
- Screenshots: artifacts/phone-before.png (latest result overview), phone-result-before.png, phone-Attraction-Map.png, phone-Daily-Itinerary.png, phone-Knowledge-Graph.png.
- Existing artifacts/navigation-smoke.cjs tests navigation and mobile layout with a fixture, including 320/390/430/768 widths. Last run passed, but mocked map API is NOT evidence of actual map rendering.
- artifacts/inspect-mobile.cjs and mobile-inspect.png are desktop Chrome viewport diagnostics, not real phone tests.
- Bundled Playwright require path: set NODE_PATH=C:\Users\god\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules before node scripts.
- Local Vite was running at http://127.0.0.1:17863; recheck before using. adb reverse can expose a local development server to phone if needed.
- Earlier frontend tests (18) and build passed. Two mobile structural tests were added afterwards; rerun current npm test and npm run build. Last full build had pre-existing missing legacy asset/bundle-size warnings.
- No fix has been verified on real phone yet. Mobile changes and navigation commit have NOT been deployed in this session.

## Staging and credentials

- Public staging: https://staging.elonmusk0.asia, protected with whole-site BasicAuth.
- Credentials JSON is stored privately at C:\Users\god\.codex\private\journeyops-staging\access.json. Read only for authenticated tooling; never print/store credentials in code, logs, prompts, or Git.
- Phone Chrome already authenticated.
- SSH alias oracle-cpamp. Repository /opt/tripstar/JourneyOps-staging. Remote base was 732d191; verify again before deploying.
- Staging API container helloagents-trip-planner-staging, image journeyops-app:branding-732d191, loopback 17861. Worker journeyops-worker-staging uses an older image; do not restart worker.
- Production container helloagents-trip-planner, public https://elonmusk0.asia, loopback17860. Record fresh container/image/restart baseline and verify unchanged after staging deployment.
- Existing Caddy protection injects API access code, strips Authorization before proxying. Do not dump Caddy import or .env.staging (secrets).
- Server private credentials /opt/tripstar/private/staging-access.json. Existing untracked .env.demo.backup.amap.20260820T031935Z must be preserved.

## Deployment pattern

- Read existing docs/DEPLOYMENT.md and artifacts/branding-release/{Dockerfile,deploy.sh}.
- Prior pattern: build local frontend; create a frontend-only image FROM journeyops-app:branding-732d191, COPY dist to /app/frontend/dist, chown journeyops.
- Transfer release archive and git bundle; remote fast-forward only after checking expected HEAD and worktree.
- Back up .env.staging privately, update only IMAGE_TAG. Recreate only trip-planner with existing staging compose files, --no-deps --no-build. Do not restart worker or migrate database.
- Keep previous image tag for rollback; restore staging image only on failure.
- Verify public TLS, unauthorized401, authenticated200, new asset hashes, and unchanged production.
- Prefer transferred shell scripts over piping PowerShell here-strings to bash (CRLF previously caused exit 0 carriage-return failure).

## AMap phone test

- Walking/transit navigation implementation is in frontend/src/services/navigation.ts, PlaceNavigation.vue, TripNavigator.vue, with zh/en/ja/ko translations.
- Direct navigation requires valid coordinates and AMap-looking POI ID; missing/uncertain places use search fallback. Completion is manual and local-only.
- Official remote MCP previously tested successfully with existing server web-service key; no new key needed. Do not expose it.
- Temporary artifacts/amap-test.html already contains two Xi'an POIs and a real generated personal-map deep link. Inspect this file rather than duplicating token in docs.
- It is not deployed. Copy to frontend/dist/amap-test.html AFTER build for this release only; do not commit transient token as frontend source.
- Intended test URL https://staging.elonmusk0.asia/amap-test.html.
- MCP link generation passed, but phone opening and token lifetime remain unverified. User gesture in Chrome and installed AMap app are required; do not claim whole-itinerary turn-by-turn navigation works.

## Next steps

1. Recheck dirty worktree and phone connection; preserve all existing edits.
2. Trace NaN map error from real Xi'an data; add finite/range validation and an honest empty/invalid-data state without inventing coordinates.
3. Complete mobile layout fixes and targeted tests; include native touch access, header actions, card clipping, map, daily itinerary, graph, and navigation controls.
4. Build and run tests. Validate on actual phone before/after staging release, not solely desktop viewport emulation.
5. Deploy only approved staging changes and temporary AMap test page, verify authentication and production unchanged.
6. Report precisely what is fixed, what passed on phone, and what remains unverified. No promise of background continuation.
