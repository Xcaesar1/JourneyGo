# AMap Website Enablement Handoff

> 命名说明：本文中的名称已统一为 JourneyGo，历史服务器标识请查阅提交 `def71ad` 中的原文件；本次未迁移线上环境。升级前阅读仓库 `docs/BRANDING_MIGRATION.md`。

## Completed Follow-Up (2026-09-18)

- Staging API now persistently has `AMAP_PERSONAL_MAP_ENABLED=true` through
  `/opt/journeygo/releases/amap-enable-20260918/amap-enable.compose.yaml`.
  Historical statements below describe the pre-enablement handoff.
- Real Android Chrome day-2 export was confirmed twice with the exact identity
  below; both responses reused the original six-point link. Browser touch on
  the open-app link successfully opened the existing JourneyGo Shanghai map.
- Disabled/failed UI responses were verified using browser-only mocks, with
  individual navigation retained. Homepage/readiness passed; production, worker
  and data containers were unchanged. Pending application edits were not deployed.
- See `DEPLOYMENT.md` for release details and API-only rollback instructions.
- Post-browser database hashes match the pre-enablement baseline: map ledger
  remains 1 succeeded entry; tasks, reviews, versions and travel queries unchanged.

## User Request And Authorization

- User requests enabling the website-wide AMap personal-map export feature, not another isolated test.
- Default target is staging at https://staging.elonmusk0.asia. Production remains out of scope.
- User explicitly approved creating a map despite unknown billing: "直接创建，这边没有提示收费".
- Latest instruction: "转移给新会话，将网站全局开关开启。要的是这个功能".
- Do not repeat the same billing-confirmation question. No purchase, subscription or new account authorization is approved. Do not claim the service is free.
- Latest request authorizes staging feature enablement. Do not infer permission to publish unrelated pending fixes or modify production.

## Workspace And Deployment

- Workspace: Q:/VPS/JourneyGo, branch main. Current HEAD: 9be791b.
- SSH alias: oracle-cpamp. Deployment working directory: /opt/journeygo/JourneyGo-staging.
- API container: journeygo-staging, image journeygo-app:form-help-9be791b.
- Worker container: journeygo-worker-staging, image journeygo-app:brand-cleanup-a5ccfb1.
- Current API release: /opt/journeygo/releases/form-help-9be791b-20260918.
- Global AMAP_PERSONAL_MAP_ENABLED remains false. Credentials already exist server-side; never print or expose them.
- Deployed Compose configuration is layered. Obtain the active config_files label from docker inspect; append a narrow override setting AMAP_PERSONAL_MAP_ENABLED=true. Do not replace the historical overrides or rebuild from the stale host checkout.
- Preserve distinct API/Worker image tags, paid-flight disablement, provider quotas, database volumes, authentication and ingress.
- Before any recreation, run the existing read-only active-task check at /opt/journeygo/releases/travel-d7f99ce-20260916/travel-active-check.py inside Worker. Wait if active tasks exist.
- Save previous Compose file list for rollback. Recreate only services whose config must change. No database migration is needed.

## Existing Verified Map: Reuse, Do Not Recreate

- Saved task: task_38233327d7724c9bb0c6.
- Applied review: review_80ff9e58dcfb4d9bb41b.
- Export identity: review_id above, version=null, day_index=1 (2026-09-21), confirmed=true.
- One authorized export succeeded with six points and no omissions. It used the existing export_map function and durable TravelQuery ledger, with a process-local flag override only.
- Returned URI scheme: amapuri://workInAmap/createWithToken.
- Android AMap rendered "JourneyGo 上海旅行", markers and the daily route. No purchase or permission prompt appeared; actual billing has not been checked.
- Local ignored artifact artifacts/approved-personal-map-result.json holds the returned link. Treat its token as private; never commit or print it.
- Screenshot: artifacts/journeygo-map-created-android.png.
- Reuse the same review/day identity for website testing. Changing review_id to version or switching scope can create another map. Do not delete existing ledger entries or retry uncertain sends.
- Existing export_map returns cached successful results before checking the feature flag. Verify one cached result is reused when testing the website.

## Required Acceptance

1. Enable the persistent staging feature switch, retaining explicit user confirmation before sending itinerary places.
2. On the actual website in Android Chrome, open the saved trip, expand day 2, use the export control, retrieve the existing result and click "打开高德 App".
3. Verify the browser-to-App handoff, not merely an adb VIEW intent. The earlier successful test only proved the latter.
4. Confirm ledger count does not increase for repeated same-scope retrieval. Verify disabled/failed states still have clear explanations and individual-place navigation.
5. Confirm authenticated homepage/readiness, production and data container identities, and that no trip was regenerated, reviewed or overwritten.
6. Report the actual switch state and verification result. Update deployment documentation without committing private artifacts.

## Android

- adb: Q:/Android/platform-tools/adb.exe; serial A4UF6R6206005438; package com.autonavi.minimap.
- Chrome CDP: adb forward tcp:60445 localabstract:chrome_devtools_remote.
- Existing real Chrome page is the saved staging task above. Do not inspect unrelated tabs or phone data.
- Native touch via CDP works. Do not accept unrequested location/login permission prompts silently.

## Pending Local Changes: Preserve

- Wikipedia explicit parenthesized aliases; no fuzzy article substitution.
- Hotel photo preservation and manual photo display; no automatic extra supplier lookup.
- Remove dense raw one-click overview text; preserve structured warnings and cost exclusions.
- Enrich saved transfer row labels/navigation for departure station, arrival station to hotel, and hotel to return station without modifying snapshots.
- Personal-map capability field and UI disabled-state explanation. These are not yet deployed.
- Related files: backend/app/api/v2/travel.py; backend/app/services/attraction_intro.py; backend/app/services/one_click_travel.py; frontend/src/components/{HotelPhoto,OverviewAttractionCard,PersonalMapExport,PlaceNavigation,TravelSummary}.vue; frontend/src/services/transferDetails.ts; frontend/src/views/Result.vue; related tests and docs.
- Last verification: 51 frontend tests, 47 targeted backend tests, production build and Ruff passed; fixture UI passed at 390/1440px and actual Android with zero business POST.
- This handoff does not require deploying all those unrelated changes to enable the already-deployed export endpoint. Preserve the dirty worktree; do not reset or overwrite it.
