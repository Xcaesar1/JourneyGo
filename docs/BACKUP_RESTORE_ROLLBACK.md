# Backup, Restore And Rollback

> 阶段 2 起 PostgreSQL 是任务事实源。本文保留阶段 0 的旧生产基线证据；多服务 staging
> 的数据库备份、恢复和迁移回滚以 `docs/DEPLOYMENT.md` 为准。

本说明适用于当前单容器 + Docker named volume 的 TripStar 基线。所有命令在 Oracle 主机执行。命令不得使用 `set -x`，不得打印 `.env`、`runtime_settings.json`、Cookie、API key 或 Basic Auth 内容。

## 1. 当前备份证据

阶段 0 已在以下受限目录完成一次在线、crash-consistent 备份：

```text
/var/backups/tripstar/20260806T045151Z
```

目录权限为 `0700`，归档和校验文件权限为 `0600`。包含：

- `repository.bundle`：全部已提交 Git refs；
- `working-tree.tar.gz`：包含阶段 0 前 dirty 修改的源码工作树，不含 `.git`；
- `trip_data.tar.gz`：生产 named volume 在线只读快照；
- `SHA256SUMS`：归档校验和；
- 独立 `.env` 副本仅在源文件实际存在时创建；本次仓库未发现 `.env` 文件。

在线卷备份没有停容器，因此是 crash-consistent，不等价于应用停写后的一致快照。当前数据是单文件原子替换的 JSON，风险较低，但恢复演练仍应在 staging 完成。

## 2. 创建新备份

先设置 UTC 时间戳和受限目录：

```bash
set -euo pipefail
REPO=/opt/tripstar/TripStar
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/var/backups/tripstar/$STAMP
sudo install -d -m 0700 /var/backups/tripstar "$BACKUP"
```

备份 Git 历史和当前工作树：

```bash
git -C "$REPO" bundle create /tmp/tripstar-repository.bundle --all
sudo install -m 0600 /tmp/tripstar-repository.bundle "$BACKUP/repository.bundle"
rm -f /tmp/tripstar-repository.bundle
sudo tar -czf "$BACKUP/working-tree.tar.gz" \
  --exclude='TripStar/.git' \
  -C /opt/tripstar TripStar
sudo chmod 0600 "$BACKUP/working-tree.tar.gz"
```

在线只读备份生产数据卷：

```bash
VOLUME_DATA=/var/lib/docker/volumes/tripstar_trip_data/_data
sudo test -d "$VOLUME_DATA"
sudo tar --numeric-owner -czf "$BACKUP/trip_data.tar.gz" -C "$VOLUME_DATA" .
sudo chmod 0600 "$BACKUP/trip_data.tar.gz"
```

如存在 `.env`，只复制到受限目录，不输出内容：

```bash
for FILE in .env backend/.env frontend/.env; do
  if test -f "$REPO/$FILE"; then
    SAFE_NAME=${FILE//\//_}
    sudo install -m 0600 "$REPO/$FILE" "$BACKUP/$SAFE_NAME"
  fi
done
```

生成并验证校验和：

```bash
sudo find "$BACKUP" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
  | sudo sort -z \
  | sudo xargs -0 sha256sum \
  | sudo tee "$BACKUP/SHA256SUMS" >/dev/null
sudo chmod 0600 "$BACKUP/SHA256SUMS"
sudo git -C "$REPO" bundle verify "$BACKUP/repository.bundle" >/dev/null
sudo tar -tzf "$BACKUP/working-tree.tar.gz" >/dev/null
sudo tar -tzf "$BACKUP/trip_data.tar.gz" >/dev/null
sudo sha256sum -c "$BACKUP/SHA256SUMS" >/dev/null
```

## 3. 从 Git 重新部署

先确认工作树和目标提交，不得覆盖未提交改动：

```bash
cd /opt/tripstar/TripStar
git status --short --branch
git fetch --prune origin
git log --oneline --decorate -5 origin/main
```

只有工作树状态和目标提交已人工确认后，才允许更新和重建：

```bash
git merge --ff-only origin/main
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl --fail --silent --show-error http://127.0.0.1:17860/health
curl --fail --silent --show-error http://127.0.0.1:17860/health/live
curl --fail --silent --show-error http://127.0.0.1:17860/health/ready
```

不要使用 `git reset --hard` 或 `git checkout --` 处理生产 dirty 文件。

## 4. 恢复到 staging 演练

准备只在主机保存的 staging Secret 文件：

```bash
cd /opt/tripstar/TripStar
cp .env.staging.example .env.staging
chmod 0600 .env.staging
```

填充 `.env.staging` 后先验证合并配置，不启动服务：

```bash
docker compose -p tripstar-staging \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  config --quiet
```

需要进行恢复演练时，先创建 staging volume，再把备份恢复到 staging volume，禁止写生产卷：

```bash
docker volume create tripstar_staging_data >/dev/null
STAGING_DATA=/var/lib/docker/volumes/tripstar_staging_data/_data
sudo test -d "$STAGING_DATA"
sudo tar -tzf /var/backups/tripstar/<STAMP>/trip_data.tar.gz >/dev/null
sudo tar --numeric-owner -xzf /var/backups/tripstar/<STAMP>/trip_data.tar.gz \
  -C "$STAGING_DATA"
```

确认目标是 `tripstar_staging_data` 后，才可启动 staging：

```bash
docker compose -p tripstar-staging \
  --env-file .env.staging \
  -f docker-compose.yaml \
  -f docker-compose.staging.yaml \
  up -d --build
curl --fail --silent --show-error http://127.0.0.1:17861/health/ready
```

阶段 0 只创建和验证配置，未执行上述 staging 启动或恢复命令。

## 5. 生产数据恢复

生产恢复是破坏性操作，必须满足全部前置条件：

1. 已安排维护窗口并通知使用者；
2. 已对当前状态再做一次新备份；
3. 已在 staging 验证目标归档可恢复；
4. 已记录目标卷的绝对路径和归档 SHA-256；
5. 已确认恢复会覆盖当前生产数据。

停止服务并再次校验目标：

```bash
cd /opt/tripstar/TripStar
docker compose stop trip-planner
PRODUCTION_DATA=/var/lib/docker/volumes/tripstar_trip_data/_data
sudo test "$(readlink -f "$PRODUCTION_DATA")" = \
  /var/lib/docker/volumes/tripstar_trip_data/_data
sudo sha256sum -c /var/backups/tripstar/<STAMP>/SHA256SUMS
sudo tar -tzf /var/backups/tripstar/<STAMP>/trip_data.tar.gz >/dev/null
```

只有操作者显式设置确认变量后才清空并恢复：

```bash
export CONFIRM_TRIPSTAR_PRODUCTION_RESTORE=yes
test "$CONFIRM_TRIPSTAR_PRODUCTION_RESTORE" = yes
sudo find "$PRODUCTION_DATA" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
sudo tar --numeric-owner -xzf /var/backups/tripstar/<STAMP>/trip_data.tar.gz \
  -C "$PRODUCTION_DATA"
```

启动并验证：

```bash
docker compose up -d trip-planner
curl --fail --silent --show-error http://127.0.0.1:17860/health/ready
docker compose logs --tail=100 trip-planner
```

日志检查只确认错误类型，不复制包含凭据或用户输入的完整行。

## 6. 代码回滚

共享分支优先使用可审计的 revert，不改写历史：

```bash
cd /opt/tripstar/TripStar
git status --short --branch
git show --stat <BAD_COMMIT>
git revert <BAD_COMMIT>
docker compose up -d --build
curl --fail --silent --show-error http://127.0.0.1:17860/health/ready
```

如果坏提交还未推送且工作树存在无关修改，不执行 reset。先用 `git diff`、备份和独立 revert commit 保留证据。

## 7. 阶段 0 回滚边界

阶段 0 提交只应包含：长期规范、基线审计、备份恢复文档、健康路由、健康测试、staging override、staging env 示例和 Legacy Fixtures。回滚该提交不会删除生产数据卷，也不会自动停止生产；回滚后需要重建容器，旧 `/health` 仍应存在。
