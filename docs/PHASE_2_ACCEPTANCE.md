# Phase 2 Acceptance

## Scope

只验收 PostgreSQL、Redis、Celery 和持久任务，不包含 LangGraph 或阶段 3 工作。

## Requirement Matrix

| Requirement | Implementation | Verification |
| --- | --- | --- |
| PostgreSQL, Redis, Celery | Compose services and isolated staging volumes | Compose health and Oracle staging |
| SQLAlchemy 2, Alembic | ORM models and revision `20260807_01` | Upgrade/current and CI |
| Three base tables | `trips`, `trip_tasks`, `trip_versions` | Migration inspection |
| Persist then dispatch | legacy and V2 POST routes | API contract tests |
| Legacy Planner on Worker | Celery adapter calls unchanged Planner | Worker orchestration test and staging |
| DB progress + Pub/Sub | progress callback commits then publishes | unit and Redis integration test |
| WebSocket without memory Queue | legacy and V2 subscribe to Redis | source audit and staging |
| Cancel, retry, idempotency | V2 actions, payload conflict detection and DB unique constraints | API/repository tests |
| Worker/API restart | startup/periodic recovery, persisted claim and independent DB sessions | policy tests and staging restart drill |
| Healthchecks | API, PostgreSQL, Redis, Worker | tests and Compose status |

## Automated Commands

```bash
python -m ruff check backend/app/api/v2 backend/app/db backend/app/domain \
  backend/app/workers backend/app/services/task_events.py backend/tests tests
python -m ruff check backend/app --select E9,F63,F7,F82
python -m pytest
docker compose --env-file .env.staging.example \
  -f docker-compose.yaml -f docker-compose.staging.yaml config --quiet
```

真实集成测试需要设置 `TEST_DATABASE_URL` 和 `TEST_REDIS_URL`，并先执行 Alembic upgrade。

## Executed Evidence

执行日期: 2026-08-07。目标为 Oracle 隔离 staging；生产容器、生产数据和
`trip_planner_agent.py` 均未修改。

| Check | Result |
| --- | --- |
| Local Ruff | 两组检查均通过 |
| Local pytest | `42 passed, 2 skipped`；跳过项为需要真实 PostgreSQL/Redis 的集成测试 |
| Local frontend build | `npm run build` 通过；仅保留既有资源/分块告警 |
| Alembic | revision `20260807_01` 升级成功，创建 `trips`、`trip_tasks`、`trip_versions` |
| Real PostgreSQL/Redis integration | Oracle disposable test container: `2 passed` |
| API restart | 任务在 API 重启后仍可查询 |
| Multiple API instances | 临时第二 API 实例可查询第一实例创建的同一任务 |
| Cancellation and idempotency | 取消后保持 `cancelled`；相同键/请求返回原任务，不同请求返回 `409` |
| Worker restart policy | 跨线程锁续租、丢失 broker 消息周期恢复、并发 recovery claim 和 live-lock 保护均有回归测试 |
| Redis Pub/Sub WebSocket | `websocket_pubsub=pass initial=queued final=cancelled` |
| Celery registration | Worker 注册 `journeyops.plan_trip`，`inspect` 返回一个在线节点 |
| Staging health | PostgreSQL、Redis、API、Worker healthy；`migrate` 退出码 `0` |
| API health | `/health/live` 为 alive；`/health/ready` 的 data directory、database、redis 均 ready |
| Database terminal-state audit | 验收任务只存在 `cancelled` 和 `failed`，无 queued/processing 遗留 |

旧版 HTTP 路由已真实投递到 Celery Worker，Worker 调用了未修改的 legacy Planner。由于 staging
故意不加载生产 Secret，该次外部小红书访问按策略重试三次后以脱敏 `planner_failed` 终止；这验证
了队列和失败持久化路径，不作为外部供应商成功测试。

验收后 PostgreSQL 逻辑备份位于 `/var/backups/tripstar/20260807T115742Z`；自定义格式 dump 和
SHA-256 校验文件均为 `0600`，校验通过。

## Residual Risks

- Planner 仍是 legacy 单体逻辑，只有在进度回调边界检查协作式取消。
- Redis Pub/Sub 不重放丢失事件；客户端重连后依靠数据库快照恢复。
- Worker 被强制终止后，恢复延迟受周期扫描间隔、任务锁 TTL 和 stale threshold 影响。
- 阶段 2 不迁移旧 JSON 历史数据；迁移并在 staging 核对前不得提升为 production。
- 隔离 staging 未加载生产外部服务 Secret，因此本阶段未把一次完整供应商成功响应作为验收条件。
