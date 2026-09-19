# Deployment And Rollback

> 命名说明：本文中的名称已统一为 JourneyGo，历史服务器标识请查阅提交 `def71ad` 中的原文件；本次未迁移线上环境。升级前阅读仓库 `docs/BRANDING_MIGRATION.md`。

## Mobile Cleanup And Airport Transfers (2026-09-19, Latest)

- UI `a2599a1` simplified the overview, removed the weather coverage paragraph, localized weather descriptions and fixed date/icon overlap. Staging API image `journeygo-app:ui-a2599a1`; worker was initially unchanged.
- New Chengdu live verification exposed estimated airport transfers exceeding the commute cap. `23bb1cc` adds evidenced public-transit/driving comparison for flight airport/hotel legs at least 10 km apart, without relaxing commute or check-in constraints. Current staging images: `journeygo-app:cities-api-23bb1cc` and `journeygo-app:cities-worker-23bb1cc`.
- Release directories: `/opt/journeygo/releases/ui-a2599a1-20260919` and `/opt/journeygo/releases/airports-23bb1cc-20260919`. Both deployments checked active_tasks=0, preserved the Compose chain including quota 15, and compared task state, quota and protected containers before/after. No production changes or migrations.
- Both current services healthy; deployed index/Result JS hashes match the local build. Full backend regression passed with four infrastructure skips; frontend 69 tests, Ruff and build passed. Existing build warnings about legacy assets and large bundles remain.
- Rollback with the selected release's `previous-compose-files.txt` in recorded order and `.env.staging`, after checking active tasks. Recreate only the services changed by that release. Never reset the quota counter or overwrite live task data.
- Latest new-city evidence, limitations and recovery details: [round three](demo/mobile-e2e/20260919-r3/README.md). Earlier records below are historical.

## Staging Flight Quota 15 And Mobile Retest (2026-09-19)

- User explicitly authorized raising the total flight-call limit from 10 to 15. Applied `TRAVEL_FLIGHT_CALL_LIMIT=15` to staging API and worker only, retaining the existing Compose chain and `fbd5a45` images.
- Overlay and verification evidence: `/opt/journeygo/releases/quota15-20260919/`. Both services healthy; active tasks were zero before recreation. Counter, task data and protected production state matched before/after; no counter reset or database replacement.
- End-of-test counter: 8 used, 7 remaining. This round made no new paid flight calls: Lijiang recovered with unchanged retained quotes. Any further quota increase requires authorization.
- Real Android verification completed and approved both fresh Wuhan rail and recovered Lijiang flight itineraries. See [round-two evidence](demo/mobile-e2e/20260919-r2/README.md). Older quota and blocked-phone entries below are historical.

## Nationwide Flight City Registry (2026-09-18)

- Source `55c42d4`; staging API `journeygo-app:cities-api-55c42d4`, worker
  `journeygo-app:cities-worker-55c42d4`. Release directory:
  `/opt/journeygo/releases/cities-55c42d4-20260918`.
- Replaces the small whitelist with 254 sourced mainland aviation city/place
  entries and explicit aliases. Backend planning and public quote-form mapping
  share the same snapshot; see `FLIGHT_CITY_REGISTRY.md` for scope and refresh.
- Verified 372 targeted backend tests, 60 frontend tests, Ruff and production build.
  Local and deployed desktop/mobile browser checks passed for Shenzhen-Wuhan,
  Mangshi/Shangri-La, Beijing/Chengdu and Hangzhou/Urumqi. Deployed public city
  mapping matched the checked-in snapshot. Browser quote calls remained mocked.
- Both services healthy; zero active tasks before deployment. Paid-call counter,
  task/review/version/query hashes, production/demo/data container identities unchanged.
  Flight remains enabled with cumulative limit 10; no live supplier calls, no bookings.
- Rollback: use `previous-compose-files.txt` with `.env.staging` in recorded order,
  check active tasks, then recreate only `worker trip-planner`. Previous images are
  `flight-api-b061105` and `flight-worker-b061105`. Preserve counters and data.

## Staging Flight Enablement (2026-09-18)

- User approved enabling staging flights with a cumulative limit of 10 calls.
  Do not increase the limit or reset the shared credential counter without approval.
- Source `b061105`; API `journeygo-app:flight-api-b061105`, worker
  `journeygo-app:flight-worker-b061105`. Release
  `/opt/journeygo/releases/flight-b061105-20260918` appends persistent
  `TRAVEL_FLIGHT_ENABLED=true` and `TRAVEL_FLIGHT_CALL_LIMIT=10` for both services.
- Existing supplier credential, access protection and paid consent are retained.
  Production, demo and data containers are unchanged. No migrations or bookings.
- Kunming `KMG` and Lijiang `LJG` were added to planning and quote-form mappings;
  the quote form also now includes the existing Xi'an `SIA` mapping.
- Two real, metered supplier calls succeeded: KMG-LJG on September 20 returned
  MU5919 and LJG-KMG on September 24 returned MU5920. Both passed direct-economy
  planning filters. Reference fares were CNY 280 and CNY 920 per person, excluding
  unverified taxes; these are historical probe results, not a fare guarantee.
- Counter after verification: 2 used, 8 remaining. Captured supplier responses are
  retained privately in `/opt/journeygo/releases/flight-enable-20260918`; do not repeat
  calls just to inspect them. A new uncached round trip normally consumes two calls.
- 88 targeted backend tests, 60 frontend tests, Ruff and frontend build passed.
  Both services passed health/config/quota checks. Live authenticated capability
  and missing-consent rejection passed. Deployed desktop/mobile submission and
  result UI passed with mocked task responses; no real complete itinerary was generated.
- Existing task/review/version/query hashes matched before/after deployment.
  Do not resume the user's existing train task or change its mode automatically.
- Rollback: use this release's `previous-compose-files.txt` in recorded order with
  `.env.staging`, after the active-task check, and recreate only `worker trip-planner`.
  This restores the previous disabled flight settings. Never roll back quota counters.

## Contextual Pause Choices (2026-09-18)

- Source `0aa75b1`; staging API image `journeygo-app:recovery-0aa75b1`, based on
  `journeygo-app:train-c-api-588213d`. Worker remains `journeygo-app:train-c-worker-588213d`.
- Release `/opt/journeygo/releases/recovery-0aa75b1-20260918` contains the frontend
  archive, Dockerfile, deployment script, Compose override and previous Compose file list.
- Pause UI explains model uncertainty separately from unavailable trains, retains
  specific server reasons, and offers two or three contextual actions. Budget and
  hotel choices state their changes before submission. Manual-edit choices focus
  the relevant field without submitting. Flight consent and server guards remain intact.
- Verified 60 frontend tests, production build, authenticated ingress/readiness,
  and deployed Chrome desktop/mobile interaction with mocked API responses.
  Confirmed unchanged request/no quote refresh on model retry and explicit budget
  change on the budget action. No real task continuation or supplier queries were sent.
- Zero active tasks before deployment. Task/review/version/query hashes and all
  protected production, demo, worker and database container identities were unchanged.
- Rollback using the release's `previous-compose-files.txt` in recorded order,
  `.env.staging`, and `up -d --no-deps --no-build trip-planner` after the active-task check.
  Do not recreate the worker or modify data. Personal-map enablement is preserved.

## Planning Recovery And Form Alignment (2026-09-18)

- Source `f1efb26`; API and Worker image `journeygo-app:recovery-f1efb26`.
- Release directory `/opt/journeygo/releases/recovery-f1efb26-20260918`.
- Includes feasible-plan recovery, advisory notices, responsive form alignment and
  obsolete planning-document cleanup. No database migration or dependency change.
- Backend suite passed with four integration tests skipped locally; 48 frontend tests,
  production build and pre-release Android form/calendar touch checks passed.
- Both staging services passed health, feature-gate, route and asset checks; authenticated
  ingress passed. Production, demo, PostgreSQL and Redis container identities were unchanged.
- No real task was resumed or approved. Flights and personal-map writes remain disabled.
- Rollback: read this release's `previous-compose-files.txt`, use those Compose files
  in their recorded order with `/opt/journeygo/JourneyGo-staging/.env.staging`, check
  for active tasks, then run `up -d --no-deps --no-build worker trip-planner`.
  The previous image is `journeygo-app:costs-f784506`; preserve all data volumes.

## Mobile UI Release (2026-09-17)

- Source `4129750`; staging API image `journeygo-app:mobile-4129750`.
- Release directory `/opt/journeygo/releases/mobile-4129750-20260917` contains
  the frontend archive, layered Dockerfile, deployment script and Compose override.
- Keeps text over the mobile hero with `cover` and `80% center` focus. Compact
  mobile controls and white form copy are included. Desktop hero is unchanged.
- Frontend-only release layered on `journeygo-app:one-click-f35652d`; only the
  staging API container was recreated. Worker, production API, PostgreSQL and
  Redis identities/start times were verified unchanged. No migration or quota change.
- Health, authenticated ingress and feature capabilities passed. Connected Android
  Chrome was reloaded on the actual staging URL; right-focused hero, compact
  memories control and white hints were verified. No trip/provider query submitted.
- Rollback: use the existing base/staging/travel/one-click Compose stack without
  `mobile.compose.yaml`, and `up -d --no-deps --no-build trip-planner` only.
  Keep the one-click override so enabled workflow settings are preserved.

本文件描述阶段 8 多服务架构。生产环境在明确批准前不得执行本阶段部署；当前部署目标是
Oracle staging，使用独立端口、独立 named volumes 和可回滚的镜像标签。

## Keyless Demo

### One-click Travel Release Gate

`ONE_CLICK_TRAVEL_ENABLED` defaults to `false` in the shared API/Worker environment.
Keep it off until separately approved isolated staging acceptance. Migration
`20260917_07` is additive: `trip_tasks.pending_input` and `travel_queries`.
Apply it using the existing `migrate` service before enabling the flag; do not run
an automatic downgrade or delete query/authorization records when rolling back.
The current local run only verified PostgreSQL SQL generation, not an online
PostgreSQL/Celery migration. Docker's Linux engine was unavailable.

Release checklist:

1. Confirm staging target, independent database/Redis volumes and backups.
2. Run backend tests, frontend tests/build and `tests/one-click-ui.cjs` with mocked
   providers; verify `tests/travel-ui.cjs` still covers legacy export/navigation.
3. Apply the migration in the approved staging environment and test Worker restart,
   input pause/continue and final version approval through the real task stack.
4. Verify train/hotel/AMap/model configuration. Keep `TRAVEL_FLIGHT_ENABLED=false`
   and do not change `TRAVEL_FLIGHT_CALL_LIMIT` without separate cost approval.
5. Enable `ONE_CLICK_TRAVEL_ENABLED=true` on both API and Worker only after the
   staging acceptance passes. Check mobile and desktop from a fresh browser.
6. Roll back by setting the feature flag false and restarting API/Worker. Preserve
   the ledger, timestamps, checkpoints, history and paid counters. Production is
   outside this task's authorization.

### Demo Environment

Demo 使用独立 project name、端口和数据卷，不读取真实 Provider Secret，也不发起外部模型、搜索、
地图 Web Service 或社区数据请求：

```bash
cp .env.demo.example .env.demo
chmod 0600 .env.demo
docker compose --env-file .env.demo \
  -f docker-compose.yaml -f docker-compose.demo.yaml config --quiet
docker compose --env-file .env.demo \
  -f docker-compose.yaml -f docker-compose.demo.yaml up --build -d
curl --fail --silent http://127.0.0.1:17862/health/live
curl --fail --silent http://127.0.0.1:17862/health/ready
```

公网 TLS 终止示例位于 `deploy/caddy/Caddyfile.example` 和
`deploy/nginx/journeygo.conf.example`。反向代理只应指向 loopback Compose 端口。

本地前端联调可通过 `VITE_PROXY_TARGET` 指向 API；Vite 会同时代理 HTTP 和 WebSocket：

```powershell
$env:VITE_PROXY_TARGET = 'http://127.0.0.1:8000'
npm.cmd --prefix frontend run dev
```

## Staging Deploy

### Weather MCP Release (2026-09-16)

Staging API and Worker now use the isolated Open-Meteo MCP weather release. Follow
[`WEATHER.md`](WEATHER.md) for the required Compose override, verification and per-service
rollback tags. Production is still the old single-service deployment and is unchanged.

### Mobile Frontend Release (2026-09-16)

- Source `f62e7bd`, image `journeygo-app:mobile-f62e7bd`, staging only.
- Frontend-only layer based on `journeygo-app:branding-732d191`; includes walking/transit
  controls, mobile layout/map lifecycle fixes and temporary `/amap-test.html`.
  The temporary page token is not in Git. No API/schema/history changes.
- Release directory `/opt/journeygo/releases/mobile-20260916` contains deployment script,
  private env backup and before/after production/worker container snapshots.
- Verified 23 frontend tests, build, supplemental fixture smoke, real Android touch
  navigation and actual AMap tiles/markers before and after publication. See
  `MOBILE_HANDOFF.md` for exact test scope and remaining native-app uncertainty.
- Anonymous homepage/test page/readiness 401, authenticated 200, TLS verified;
  deployed JS/CSS match local build. Production and worker snapshots unchanged.
- Roll back only staging frontend, without migrations or worker restart:

```bash
cd /opt/journeygo/JourneyGo-staging
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=branding-732d191/' .env.staging
docker compose --env-file .env.staging -f docker-compose.yaml -f docker-compose.staging.yaml up -d --no-deps --no-build trip-planner
curl --fail --silent http://127.0.0.1:17861/health/ready
```

The earlier HTTPS entry section below records its original deployment snapshot.

### Private HTTPS Entry (2026-09-16)

- Authorized staging URL: `https://staging.elonmusk0.asia`. Cloudflare A record points to
  `158.101.42.174` in DNS-only mode; HTTP redirects to HTTPS. Production and demo hostnames are unchanged.
- `/etc/caddy/Caddyfile` imports `/etc/caddy/journeygo-staging.caddy`. The imported file is
  `root:caddy`, mode `0640`; it contains the independent Basic Auth hash and upstream access code.
  Never print or commit this file. Authentication covers both frontend and API/WebSocket paths.
- Caddy strips the browser Authorization header and supplies `X-Access-Code` to loopback port `17861`.
  Staging `.env.staging` enables `API_ACCESS_CODE_REQUIRED=true`; runtime secret updates stay disabled.
  The code remains server-side. Invited users share this login and staging data; this is not user isolation.
- The deployed image remains `journeygo-app:branding-732d191`. This ingress change does not deploy the
  later navigation commit, migrate databases, or restart production, worker, PostgreSQL, or Redis.
- Login credentials are in `/opt/journeygo/private/staging-access.json` (root-only, `0600`); a restricted
  local copy was delivered outside the repository. Do not include credentials in URLs, logs, or commits.
- Verified: public DNS via `1.1.1.1` and `8.8.8.8`; valid TLS; anonymous homepage/API `401`;
  authenticated homepage/settings/readiness `200`; HTTP `308`; backend missing/wrong access code `401`.
  No model task was submitted for this check. Local DNS may temporarily retain the earlier NXDOMAIN.
- Pre-change backups: `/var/backups/journeygo/staging-https-20260916T032001Z/` contains `Caddyfile` and
  `env.staging`. For an authorized rollback, first verify no subsequent unrelated Caddy edits exist,
  restore those two files to their original locations, validate/reload Caddy, then recreate only
  `trip-planner` with the staging Compose files and `--no-deps --no-build`. The separate imported site
  file becomes inactive once the original Caddyfile is restored. No data restore is required.

```bash
cd /opt/journeygo/JourneyGo-staging
git status --short --branch
git pull --ff-only origin staging
cp -n .env.staging.example .env.staging
chmod 0600 .env.staging
```

只在未跟踪的 `.env.staging` 中填写 Secret。`POSTGRES_PASSWORD` 使用随机、URL-safe 字符；
不得打印该文件。

阶段 8 部署至少显式设置以下非 Secret flags：

```dotenv
IMAGE_TAG=phase8-<short-commit>
PLANNER_ENGINE=journey_graph
PLANNER_COMPARE_ENGINES=false
LEGACY_JSON_REPAIR=true
LANGGRAPH_STRICT_MSGPACK=true
XHS_ENABLED=false
BRAVE_SEARCH_BASE_URL=https://api.search.brave.com/res/v1/web/search
WEB_RESEARCH_TIMEOUT=10
WEB_RESEARCH_RESULT_COUNT=5
SOURCE_CACHE_TTL_SECONDS=21600
API_ACCESS_CODE_REQUIRED=false
API_RATE_LIMIT_ENABLED=true
API_RATE_LIMIT_REQUESTS=6
API_RATE_LIMIT_WINDOW_SECONDS=60
API_MAX_ACTIVE_TRIP_TASKS=4
API_MAX_REQUEST_BYTES=32768
LLM_MAX_TOKENS_PER_TRIP=80000
LLM_MAX_COST_PER_TRIP_USD=2.0
DEMO_MODE=false
API_DOCS_ENABLED=false
RUNTIME_SECRET_UPDATES_ENABLED=false
```

`BRAVE_SEARCH_API_KEY` 是可选 Secret，只能保存在未跟踪的 `.env.staging`。未配置时使用 Noop
降级并将无来源的关键事实标记为 `unknown`。`WEB_RESEARCH_OFFICIAL_DOMAINS` 可配置逗号分隔的
官方域名 allowlist。XHS 默认关闭；仅在社区来源已获授权且 Cookie 已安全写入主机环境时启用。
comparison 默认关闭，避免双倍外部调用成本。

路线服务 Key、前端地图 Key 和前端安全配置同样只能保存在 `.env.staging` 或受限运行时设置中。
日志不得记录带查询参数的上游请求 URL。高德路线接口返回的是驾车距离/时长证据；系统生成的
火车或飞机方案是确定性规划估算，不得标记为实时班次、余票、可售状态或实时票价。

公网 promotion 前必须把 `API_ACCESS_CODE_REQUIRED` 改为 `true`，并在未跟踪环境中生成独立访问码。
`LLM_INPUT_COST_PER_MILLION_USD` 和 `LLM_OUTPUT_COST_PER_MILLION_USD` 必须按当前供应商账单单位填写；
代码不硬编码会变化的价格。未填写时 dollar 指标为 `0`，但 token、并发和速率上限仍强制生效。

```bash
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  config --quiet
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  build trip-planner
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  up -d --no-build
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  ps
curl --fail --silent http://127.0.0.1:17861/health/ready
```

`migrate` 必须以 `0` 退出，`postgres`、`redis`、`worker` 和 `trip-planner` 必须为 healthy。

## Database Backup

PostgreSQL 是任务事实源。部署迁移和回滚前创建逻辑备份：

```bash
set -euo pipefail
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/var/backups/journeygo/$STAMP
sudo install -d -m 0700 "$BACKUP"
docker exec journeygo-postgres-staging \
  pg_dump -U journeygo -d journeygo -Fc \
  | sudo tee "$BACKUP/journeygo-staging.pgdump" >/dev/null
sudo chmod 0600 "$BACKUP/journeygo-staging.pgdump"
sudo sha256sum "$BACKUP/journeygo-staging.pgdump" \
  | sudo tee "$BACKUP/journeygo-staging.pgdump.sha256" >/dev/null
sudo chmod 0600 "$BACKUP/journeygo-staging.pgdump.sha256"
sudo sha256sum -c "$BACKUP/journeygo-staging.pgdump.sha256"
```

Redis 不保存任务真相。通常不恢复 Redis volume；Worker 启动扫描负责处理未投递或陈旧任务。

## Restore Drill

恢复会覆盖目标数据库，只能在新的 staging 演练栈中执行，并需先确认目标容器名和卷名。

```bash
set -euo pipefail
test "$TARGET_POSTGRES_CONTAINER" = journeygo-postgres-restore-drill
docker exec "$TARGET_POSTGRES_CONTAINER" \
  dropdb -U journeygo --if-exists journeygo
docker exec "$TARGET_POSTGRES_CONTAINER" \
  createdb -U journeygo journeygo
sudo cat /var/backups/journeygo/<STAMP>/journeygo-staging.pgdump \
  | docker exec -i "$TARGET_POSTGRES_CONTAINER" \
  pg_restore -U journeygo -d journeygo --clean --if-exists \
    --no-owner --no-privileges
```

恢复后执行 `alembic current`、三表计数、`/health/ready` 和一个脱敏测试任务。禁止把恢复
演练指向生产容器或生产 volume。

## Code Rollback

先用 Feature Flag 做无数据损失的功能回滚：

```bash
sed -i 's/^PLANNER_ENGINE=.*/PLANNER_ENGINE=legacy/' .env.staging
sed -i 's/^PLANNER_COMPARE_ENGINES=.*/PLANNER_COMPARE_ENGINES=false/' .env.staging
sed -i 's/^XHS_ENABLED=.*/XHS_ENABLED=false/' .env.staging
chmod 0600 .env.staging
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  up -d --no-deps --no-build --force-recreate worker trip-planner
```

代码回滚使用审计可见的 revert，不改写历史。数据库仍在 `20260808_05` 时，回滚版本必须保留
该 revision 文件，或者跳过旧镜像的 migrate service、只替换 API/Worker；阶段 6 旧镜像中的
Alembic 不认识 `20260808_05`，不能直接运行完整 `compose up`。代码回滚不会自动删除
PostgreSQL/Redis volumes。只回滚应用时保留数据卷；确认备份可恢复且明确不再需要对应阶段的
来源数据或审核/版本审计后，才可人工执行 Alembic downgrade。不得把
`docker compose down -v` 作为常规回滚命令。

## Migration Rollback

最终 DoD 审计 revision `20260809_06` 增加追加式 `user_feedback` 表。应用回滚时优先保留该表；
若已确认反馈数据不再需要，并已有验证通过的 PostgreSQL custom dump，可在停掉 API 和 Worker 后执行：

```bash
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  stop trip-planner worker
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  run --rm migrate alembic -c backend/alembic.ini downgrade 20260808_05
```

该 downgrade 会永久删除全部用户反馈，只能在 staging 维护窗口经人工确认后执行，不得用于生产。

阶段 7 revision `20260808_05` 增加 trace、版本运行清单和脱敏遥测。应用回滚时优先保留这些
加法结构；若明确需要回退到阶段 6 schema：

```bash
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  stop trip-planner worker
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  run --rm migrate alembic -c backend/alembic.ini downgrade 20260808_04
```

该步骤会删除全部阶段 7 遥测、trace ID 和模型/Prompt/工具/工作流版本清单。必须先保存并验证
PostgreSQL custom dump；不得为回滚而删除 PostgreSQL 或 Redis volume。

阶段 6 revision `20260808_04` 增加持久审核记录、活动版本指针和版本审计字段。应用回滚时优先
保留这些加法结构；若明确需要回退到阶段 5 schema：

```bash
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  stop trip-planner worker
docker compose \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  run --rm migrate alembic -c backend/alembic.ini downgrade 20260808_03
```

该命令会删除全部审核记录、活动版本指针和版本原因/来源/校验审计字段，但保留阶段 4 来源证据。
执行前必须有已校验 `pg_dump`、维护窗口和人工批准。LangGraph checkpoint tables 不由 Alembic
revision 管理，默认保留。若还需回退到阶段 3 schema，再单独把 `20260808_03` 降到
`20260808_02`；该步骤会删除来源证据和关联。

## Production Promotion Gate

JourneyGo 新栈仍不读取或迁移 `backend/data/trip_tasks/*.json`。正式切换生产前必须先盘点旧 JSON，制定
可重复执行且已在 staging 验证的数据导入方案，并核对任务数、终态数和历史结果。该迁移未完成前，
不得将新栈提升为 production，也不得删除旧 JSON volume。公网提升还必须启用并验证应用级
访问码、确认当前模型单价，并保留现有反向代理认证。

## Executed Backup Evidence

- 2026-08-07 Oracle staging PostgreSQL backup: `/var/backups/journeygo/20260807T115742Z`
- Format: PostgreSQL custom dump plus SHA-256 manifest
- Permissions: backup directory `0700`, files `0600`
- Verification: `sha256sum -c` passed

## Phase 3 Executed Evidence

- 2026-08-08 pre-deploy backup: `/var/backups/journeygo/20260807T181543Z-phase3-predeploy`
- Deployed source: `909e8ba`; image: `journeygo-app:phase3-909e8ba`
- Alembic: `20260808_02`; migration container exit: `0`
- Staging graph task completed with native schema `2.0`, legacy client Adapter and 7 checkpoint rows
- Worker restored to `PLANNER_ENGINE=legacy`; production `/health/ready` remained ready
- Full matrix and residual risks: `docs/PHASE_3_ACCEPTANCE.md`

## Phase 4 Executed Evidence

- 2026-08-08 pre-deploy backup: `/var/backups/journeygo/20260808T005836Z-phase4-predeploy`
- Deployed source: `946cee3`; image: `journeygo-app:phase4-946cee3`
- Alembic: `20260808_03`; staging and production readiness both remained `200`
- Real no-Key JourneyGraph task completed with 4 persisted `unknown` evidence records and no task error
- Real configured XHS call returned `unavailable` through the optional-provider boundary without failing a task
- Full matrix, browser verification and residual risks: `docs/PHASE_4_ACCEPTANCE.md`

## Phase 5 Executed Evidence

- 2026-08-08 pre-deploy backup: `/var/backups/journeygo/20260808T041757Z-phase5-predeploy`
- Deployed source: `147d93b`; image: `journeygo-app:phase5-147d93b`
- Alembic remains `20260808_03`; migration container exit: `0`; no phase 5 schema migration
- Real JourneyGraph task `task_6c97534bd3d148bd97ca` completed with explicit origin, recommended intercity
  option, closed timelines, recalculated budget, zero validation issues and zero revisions
- AMap route smoke returned `verified` with a 1,205,561 meter Beijing-to-Shanghai distance
- Five non-empty sensitive values were absent from route output, API/Worker logs and the task response
- Full matrix, browser verification and residual risks: `docs/PHASE_5_ACCEPTANCE.md`

## Phase 6 Executed Evidence

- 2026-08-08 pre-deploy backup: `/var/backups/journeygo/20260808T080347Z-phase6-predeploy`
- Deployed application source: `011a485`; image: `journeygo-app:phase6-011a485`
- Alembic: `20260808_04`; migration container exit: `0`
- Initial proposal survived API/Worker restart without creating a version; approval created V1
- Scoped day-1 replan preserved day 0, approval created V2, and rollback created active V3
- No-op approval returned `409`; later replan rejection preserved active V3 and the completed result
- Three configured non-empty sensitive values were absent from task output and API/Worker logs
- Full matrix, browser verification and residual risks: `docs/PHASE_6_ACCEPTANCE.md`

## Phase 7 Executed Evidence

- 2026-08-08 pre-deploy backup: `/var/backups/journeygo/20260808T102339Z-phase7-predeploy`
- Deployed source: `2634e73`; image: `journeygo-app:phase7-2634e73`
- Alembic: `20260808_05`; migration container exit: `0`
- Live guardrails returned missing access `401`, injection `422`, budget `429` and Redis rate `429`
- Live cost trace recorded 13,055 tokens, USD 0.00293888 and 56,579 ms on `deepseek-v4-flash`
- Review resume produced `engine_resume` without increasing token or cost totals
- Three configured sensitive values had zero matches in telemetry and API/Worker logs
- Full evaluation, trace evidence and residual risks: `docs/PHASE_7_ACCEPTANCE.md`

## Phase 8 Executed Evidence

- 2026-08-08 pre-deploy backup: `/var/backups/journeygo/20260808T132203Z-phase8-predeploy`
- Deployed source: `f6ec417`; image: `journeygo-app:phase8-f6ec417`
- Alembic: `20260808_05`; staging `17861`, keyless demo `17862`, and production `17860` readiness all returned
  `200`
- API and Worker run as non-root `journeygo`; final build has no credential build arguments or values
- Real keyless task reached every JourneyGraph stage, paused for approval, created exactly one active immutable
  version and consumed zero model tokens
- Production container ID, image, restart count and home-page SHA-256 remained unchanged
- Browser flow and screenshots: `docs/assets/phase8/`; full matrix and residual risks:
  `docs/PHASE_8_ACCEPTANCE.md`
## One-click Staging Release (2026-09-17)

- Application source: `f35652d` (includes one-click workflow `d7fe4a2`).
- URL: `https://staging.elonmusk0.asia`; existing private login unchanged.
- Image: `journeygo-app:one-click-f35652d` on staging API and Worker only.
- Release directory: `/opt/journeygo/releases/one-click-f35652d-20260917`.
  Contains source archives, layered Dockerfile, `one-click.compose.yaml`,
  `deploy.sh`, verification scripts and build log. Base dependencies match
  `journeygo-app:memories-1245377`; backend and built frontend are replaced.
- Deployment uses the original staging checkout/env plus the existing travel
  override, memories override and new one-click override. Server branch and
  its untracked private backup are not modified.
- One-click, train and hotel are enabled on both processes. Worker now also
  reads the existing private travel env file. Flights remain disabled; existing
  zero paid-call ceiling and Redis counters are preserved.
- Before migration: no active tasks; custom PostgreSQL dump saved to the release
  directory as `staging-before.dump` with `0600` permissions, verified using
  `pg_restore --list`; digest in `backup.sha256`. Treat dump as private data.
- Migration `20260809_06 -> 20260917_07` and checkpoint setup succeeded.
  API/Worker healthy; schema, private ingress, readiness and capabilities passed.
  Protected container identity/start-time comparison confirms production API,
  staging PostgreSQL and Redis were unchanged. No ingress/DNS change.
- Homepage exposes Chinese/English only; obsolete saved homepage languages
  fall back to Chinese. Existing translation packs and saved trips remain.
- No real supplier/model itinerary or paid flight was requested during release.
  Live end-to-end functional acceptance remains pending.
- Against deployed assets over an SSH loopback tunnel, `home-hero.cjs`,
  `one-click-ui.cjs` and `travel-ui.cjs` passed with mocked APIs: two languages,
  saved-locale fallback, phone/desktop layout, pause/resume, navigation, quote
  proposal editor and legacy result/export compatibility. HTTPS/auth checks
  were separately run against the public staging hostname.

For application rollback, preserve the database migration/query ledger and
paid counters. With no active tasks, recreate only API/Worker using the previous
override stack (the previous image defaults one-click to disabled):

```bash
cd /opt/journeygo/JourneyGo-staging
docker compose --env-file .env.staging \
  -f docker-compose.yaml -f docker-compose.staging.yaml \
  -f /opt/journeygo/releases/travel-d7f99ce-20260916/travel.release.compose.yaml \
  -f /opt/journeygo/releases/memories-1245377-20260917/memories.compose.yaml \
  up -d --no-deps --no-build worker trip-planner
```

Do not downgrade `20260917_07`, restore a dump over live data, reset counters,
or remove volumes as part of application rollback.

## Outdoor Handbook Staging Release (2026-09-17)

- Application source: `f136167`; target: `https://staging.elonmusk0.asia` only.
- Image: `journeygo-app:outdoor-f136167`, derived from the running
  `journeygo-app:rail-2d90633` image with only `/app/frontend/dist` replaced.
- Release directory: `/opt/journeygo/releases/outdoor-f136167-20260917`.
  Includes the production frontend build, Dockerfile, compose override, build log,
  deployment script and previous compose file list. No secrets are included in Git.
- Outdoor is the sole form/result theme. Preview switch removed; hero remains
  intact, with the form below it. Train numbers use lining/tabular figures;
  timeline curved borders and the internal validation summary are removed.
  Critical travel notices and excluded-cost information remain visible.
- Verification: 36 frontend tests and production build passed. Readiness,
  authenticated ingress, train/hotel capability and disabled paid flights passed.
  No active tasks at deployment. Worker, production, demo, PostgreSQL and Redis
  container identities/start times were unchanged. No migrations or provider calls.
- First attempt automatically rolled back when ingress verification could not
  read protected login configuration. Retry ran only that verifier with `sudo`;
  file permissions and credentials were not modified.
- Existing build warnings remain: legacy image/icon paths and large JS chunks.

Rollback only the staging API image, preserving the current compose settings:

```bash
cd /opt/journeygo/JourneyGo-staging
release=/opt/journeygo/releases/outdoor-f136167-20260917
compose=(docker compose --env-file .env.staging)
IFS=',' read -ra paths < "$release/previous-compose-files.txt"
for path in "${paths[@]}"; do compose+=(-f "$path"); done
"${compose[@]}" up -d --no-deps --no-build trip-planner
```

Do not change worker images, downgrade schema, restore data or remove volumes for
this frontend rollback.

## Mobile Calendar and Task Recovery Hotfix (2026-09-17)

- Source commits: `cfb2dfe` (calendar column clipping) and `a925c9d` (task connection recovery).
- Staging API image: `journeygo-app:mobile-fix-a925c9d`, layered on
  `journeygo-app:outdoor-f136167`; only built frontend files replaced.
- Release directory: `/opt/journeygo/releases/mobile-fix-a925c9d-20260917`.
  Use its `previous-compose-files.txt` with the rollback commands above to restore
  the outdoor image. No schema or data rollback is needed.
- Date table and all seven column widths now agree; rightmost Sunday cells are
  not clipped. September 20 was selected by touch in 360/390/768/1440px checks.
- WebSocket error/close now falls back to read-only task-status polling, rather
  than reporting generation failure. Connection recovery never resubmits work.
  Reloading a pending-review task recovers the existing draft.
- 40 frontend tests and production build passed. A simulated mobile disconnect
  against deployed frontend assets recovered pending review with zero POSTs.
- Readiness, private ingress and capability checks passed; paid flights remain
  off. Production, worker, demo and data containers were unchanged.
- The investigated real task remained awaiting approval with one attempt before
  and after deployment. No real generation, retry, supplier query or review was
  triggered by this hotfix verification.

## Navigation and Result Delivery Follow-up (2026-09-17)

- Source: `93cdca4` (shared navigation) and `f9a281d` (result delivery states).
- Staging API image: `journeygo-app:nav-progress-f9a281d`; release directory:
  `/opt/journeygo/releases/nav-progress-f9a281d-20260917`. Frontend-only layer on
  `journeygo-app:mobile-fix-a925c9d`; worker and backend remain unchanged.
- All shared navigation menus expose Chinese/English only, hide settings by
  default and retain the GitHub link at every viewport width. Legacy translation
  packs remain for data compatibility.
- Progress no longer announces 100% before a usable result arrives. Missing
  terminal-event payloads are retrieved by GET; navigation is awaited. Connection
  interruptions and page-open failures show status-recovery actions, not a task
  generation-failure prompt. Recovery never automatically regenerates a trip.
- Verification: 42 tests and production build passed; 360/390/768/1440px homepage
  and result navigation checks passed. Simulated socket interruption recovered
  the existing review with no POST requests. Private ingress, readiness and
  capability checks passed. Production, worker, demo and data containers were
  unchanged; no real supplier requests or approvals were made.
- Roll back only staging API using this release's `previous-compose-files.txt`
  and the compose rollback loop above. No data migration or restore is required.

## Trip-date Weather and Progress Scroll (2026-09-17)

- Source: `d5c8d10` (focus/scroll to generation progress) and `133a1bb`
  (one-click weather collection and missing-date notices).
- Staging API and worker image: `journeygo-app:weather-133a1bb`.
  Release directory: `/opt/journeygo/releases/weather-133a1bb-20260917`.
  Layered on `journeygo-app:nav-progress-f9a281d`, replacing frontend assets,
  JourneyGraph wiring and weather enrichment only. No dependency/API/schema change.
- Root cause: the one-click branch bypassed weather collection and returned the
  draft unchanged during enrichment. It now collects provider forecasts for each
  destination's inclusive stay dates, retaining the verified schedule and costs.
  Missing forecasts remain unavailable; existing drafts are not backfilled.
- Verification: 54 backend tests, 44 frontend tests, production build and targeted
  Ruff checks passed. Local progress scrolling passed at 360/390/768/1440px with
  reduced-motion enabled and disabled. Fixed weather fixtures cover empty and
  partial data; no real supplier calls, task creation or approval were performed.
- Deployment found zero active tasks. API/worker health, weather enablement,
  private ingress and capabilities passed; flights remain disabled with zero call
  allowance. Production, demo, PostgreSQL and Redis identities stayed unchanged.
- Deployed mobile connection recovery passed using GET only, with zero POSTs.
- Deployed empty/partial weather views passed at 390/1440px without horizontal
  overflow or POST requests, using fixed local fixtures against staging assets.
- Build retains the existing legacy asset-path and large-chunk warnings.

Rollback both staging application services, not data or schema:

```bash
cd /opt/journeygo/JourneyGo-staging
release=/opt/journeygo/releases/weather-133a1bb-20260917
docker exec -i journeygo-worker-staging python < /opt/journeygo/releases/travel-d7f99ce-20260916/travel-active-check.py
compose=(docker compose --env-file .env.staging)
IFS=',' read -ra paths < "$release/previous-compose-files.txt"
for path in "${paths[@]}"; do compose+=(-f "$path"); done
"${compose[@]}" up -d --no-deps --no-build worker trip-planner
```

This restores API `journeygo-app:nav-progress-f9a281d` and worker
`journeygo-app:rail-2d90633`. Wait for both health checks before accepting traffic.

## Staging AMap Personal Map Enablement (2026-09-18)

Subsequent application release: `d14605a`, documented in the result-details section
below, retains this API flag and updates both staging application images.

- Configuration-only release: `/opt/journeygo/releases/amap-enable-20260918`.
  Append `amap-enable.compose.yaml` to the API container's active Compose file
  list. It sets only `trip-planner.environment.AMAP_PERSONAL_MAP_ENABLED=true`.
  Tracked source: `deploy/amap-personal-map.staging.yaml`; apply only to staging.
  The previous layered file list is saved as `previous-compose-files.txt`.
- Only staging API was recreated, retaining `journeygo-app:form-help-9be791b`.
  Worker stays on `journeygo-app:brand-cleanup-a5ccfb1`; its unused map flag
  remains false. Website exports execute synchronously in the API.
- Zero active tasks before recreation. API healthy; authenticated homepage,
  `/health/ready` and travel capabilities returned 200. Paid flights remain
  disabled with zero call allowance. Production, worker, demo and data container
  identities, images and start times are unchanged.
- Actual Android Chrome validation used saved task
  `task_38233327d7724c9bb0c6`, review `review_80ff9e58dcfb4d9bb41b`,
  `version=null`, `day_index=1` (2026-09-21), `confirmed=true`.
  Two website confirmations returned the exact existing private map URL,
  six points and no omissions. A native browser touch on `Open AMap app`
  opened `com.autonavi.minimap`, displaying `JourneyGo` Shanghai trip and
  the day-2 route marker. No adb VIEW intent was used for this handoff.
- Disabled (503) and failed (502) responses were simulated in the browser only;
  both displayed the explanation and individual-place navigation fallback.
  No production flag was changed and no extra map was created for these tests.
- Before enablement and after both browser exports, full-row hashes match for
  all 2 tasks, 1 review, 1 version and 36 travel queries. The personal-map ledger
  remains exactly 1 succeeded entry. No itinerary was regenerated or overwritten.
- Private links, screenshots and verification scripts remain in ignored
  `artifacts/`; no unrelated pending application changes were deployed.
  Billing was not checked and no purchase or account permission was accepted.

Rollback only the staging API, after the active-task check:

```bash
cd /opt/journeygo/JourneyGo-staging
release=/opt/journeygo/releases/amap-enable-20260918
docker exec -i journeygo-worker-staging python < /opt/journeygo/releases/travel-d7f99ce-20260916/travel-active-check.py
compose=(docker compose --env-file .env.staging)
IFS=',' read -ra paths < "$release/previous-compose-files.txt"
for path in "${paths[@]}"; do compose+=(-f "$path"); done
"${compose[@]}" up -d --no-deps --no-build trip-planner
```

Wait for API health before accepting traffic. This restores the previous false
flag without rebuilding images, changing worker configuration or modifying data.

## Result Details and Light Map (2026-09-18)

### C-prefix Train Eligibility Follow-Up

- Source `588213d`; release `/opt/journeygo/releases/train-c-588213d-20260918`.
  API image `journeygo-app:train-c-api-588213d`; worker image
  `journeygo-app:train-c-worker-588213d`. Each is layered onto its respective
  previous image, replacing only `one_click_travel.py`; no frontend/schema change.
- C-prefix second-class trains now pass the same eligibility checks as G/D.
  Empty-candidate messages identify leg, route and date, distinguishing empty
  supplier responses from returned but ineligible offers. Query arguments and
  durable ledger identities are unchanged.
- 87 targeted backend tests and Ruff passed. After deployment, both API and worker
  accepted all 11 saved Kunming-Lijiang outbound C-train records without provider
  calls. This validates parsing of the saved quote, not current inventory or return
  availability. The paused task was not resumed and its stored prompt is unchanged.
- Zero active tasks before recreation; both services healthy; authenticated
  homepage/readiness passed. Before/after task/review/version/query hashes match.
  Production, demo and data containers are unchanged; personal-map enablement and
  paid-flight disablement remain intact.
- Rollback both staging app services using this release's saved
  `previous-compose-files.txt` and `up -d --no-deps --no-build worker trip-planner`
  after the active-task check. Restores API `carousel-8becae8` and worker
  `result-details-d14605a`; do not delete queries or rewrite tasks.

Scroll-interaction follow-up: `8becae8`, API image
`journeygo-app:carousel-8becae8`, release directory
`/opt/journeygo/releases/carousel-8becae8-20260918`. Removes mouseenter-driven
selection, which competed with wheel/drag events as cards moved under a stationary
pointer. Side cards select on click, keyboard focus remains supported, and wheel
events release to the page at either end. No visual redesign.
Verification: 55 frontend tests/build; native desktop wheel traversal across all
six fixture cards in both directions with the pointer at left/center/right; drag,
side-card click and 390/900/1440px regression checks. Deployed wheel handlers also
passed with synthetic wheel events and the same six-card fixture (Android Chrome
desktop viewport does not provide a reliable native mouse-wheel test).
Staging health/private ingress passed, map enablement stayed true, and worker,
production/demo/data containers were unchanged. Roll back API only via this
release's saved Compose list; it restores `carousel-05f5ce2`.

Subsequent gallery-only release: `05f5ce2`, API image
`journeygo-app:carousel-05f5ce2`, release directory
`/opt/journeygo/releases/carousel-05f5ce2-20260918`. Restores the original
centered coverflow with smaller depth/overlap and removes image-bottom wave
overlays for straight edges. The replacement grid and arrow-control designs
are discarded. Worker remains `journeygo-app:result-details-d14605a`.
All 54 frontend tests, production build and 390/900/1440px interaction checks
passed. Deployment found zero active tasks; private ingress/readiness and map
enablement passed, with worker, production, demo and data containers unchanged.
The actual staging page also passed desktop-viewport coverflow, straight-edge,
keyboard navigation and itinerary-link checks with zero business mutations.
Rollback only `trip-planner` using this release's `previous-compose-files.txt`
and the existing Compose loop after the active-task check. This restores the
previous API image without changing data, worker or the personal-map flag.

- Source: `d14605a`; API and worker: `journeygo-app:result-details-d14605a`.
  Release: `/opt/journeygo/releases/result-details-d14605a-20260918`.
- Layers the built frontend and three changed backend modules onto the previous
  API image. No dependency changes or migrations. Existing Compose layers and
  the persistent personal-map API enablement are retained.
- Includes the pending Wikipedia alias, hotel-photo preservation/display,
  transfer navigation and map-capability UI changes. Attraction maps now use
  the normal light style; overview photos use aligned desktop cards with mobile
  swipe browsing. Redundant daily summaries and issue pills are removed.
- Verification: 54 frontend tests, 47 targeted backend tests, changed-file Ruff,
  production build, gallery layout/action checks at 390/900/1440px and saved-trip
  fixture detail checks at 390/1440px passed. Existing legacy asset-path and
  chunk-size build warnings remain.
- Zero active tasks at deployment. API/worker health, private ingress,
  homepage/readiness, enabled map capability and paid-flight disablement passed.
  Before/after task, review, version and travel-query hashes match. Production,
  demo, PostgreSQL and Redis container identities/start times are unchanged.
- Live Android Chrome on staging confirmed the new gallery, removed daily blocks,
  hotel image controls, enabled map confirmation, rendered light AMap canvas and
  authenticated homepage/readiness. Verification sent zero business mutations.
- Rollback both staging application services using this release's
  `previous-compose-files.txt` and the Compose loop above, with
  `up -d --no-deps --no-build worker trip-planner`, after the active-task check.
  This restores API `form-help-9be791b` and worker `brand-cleanup-a5ccfb1`
  while keeping the previously enabled personal-map API flag. Do not delete data.

## Sourced Costs, Attraction Introductions and Map Export (2026-09-17)

- Source: `f784506`. Staging API and worker image: `journeygo-app:costs-f784506`,
  layered on `journeygo-app:weather-133a1bb`.
- Release: `/opt/journeygo/releases/costs-f784506-20260917`. Includes source archive,
  built frontend, Dockerfile, compose override, deployment/verification scripts,
  build log and `previous-compose-files.txt` for rollback.
- Ships short sourced attraction introductions, AMap per-person meal references,
  explicit unknown meal exclusions, budget date scopes and responsive budget rows,
  and consent-based whole-trip/day personal-map entry points.
- `AMAP_PERSONAL_MAP_ENABLED=false` is explicitly retained on both services until
  account entitlement/quota/billing are verified. Paid flights remain disabled with
  zero allowance. Weather, train and hotel capabilities remain enabled.
- Before release: 344 backend tests passed, 4 skipped; 47 frontend tests passed;
  production build passed with existing asset-path/chunk-size warnings.
- Zero active tasks at deployment. Both services healthy; database revision,
  private ingress authentication, homepage and capabilities passed. Production,
  demo and PostgreSQL/Redis container identities/start times were unchanged.
- Deployed assets passed fixed-fixture Chrome checks at 360/390/768/1440 px:
  whole/day export, confirmation, mocked failure/retry, budget dates and no
  horizontal document overflow. All map creation responses were mocked.
- Live readiness and introduction input validation passed. An empty map POST
  returned 422 before consent/snapshot validation, without creating a map or task.
  No real itinerary generation, supplier query, review or database migration.
- Android was not connected. Real personal-map creation and app handoff remain
  unverified; enabling the feature is a separate operational decision.

Rollback both application services using this release's `previous-compose-files.txt`
and the compose loop above, after checking for active tasks. It restores
`journeygo-app:weather-133a1bb` for both API and worker; do not restore/delete data.
