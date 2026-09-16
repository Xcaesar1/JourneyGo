# ADR 0001: Durable Task Architecture

- Status: Accepted
- Date: 2026-08-07
- Scope: Phase 2

## Context

原实现使用 API 进程内字典、`asyncio.create_task`、进程内 WebSocket Queue 和 JSON 文件。
API 或 Worker 重启会中断执行，且多 API 实例不能共享一致状态。

## Decision

- PostgreSQL 是 trip、task 和 version 的唯一事实源。
- Celery 通过 Redis broker 执行长任务，Worker 使用 late acknowledgement。
- Redis Pub/Sub 只发布状态快照；WebSocket 定期从 PostgreSQL 对账。
- legacy API 契约保留并适配同一持久架构。
- legacy Planner 不修改，由 Worker 在执行时延迟导入。
- 数据库唯一约束和任务状态机承担幂等，不依赖 broker 去重。

## Consequences

- API 可以横向扩展，重启不会删除任务记录。
- 部署增加 PostgreSQL、Redis、迁移和 Worker 运维成本。
- Pub/Sub 不是持久日志，重连必须先读数据库快照。
- Planner 内部暂时不能在任意指令处抢占，取消仍是协作式。
