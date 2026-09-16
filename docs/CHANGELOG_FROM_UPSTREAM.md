# Changelog From Upstream

本文件记录 JourneyOps 相对 `1sdv/TripStar` 的二次开发差异，不替代 Git 历史。

## Mobile Navigation - 2026-09-16

- 移动端结果页改用全部可见的分行导航与独立操作区；景点列表单列，概览卡片高度自适应且入口无需悬停。
- 修复旧全局导航样式使手机页头控件移出视口的问题；增加布局回归测试。使用 USB 连接的荣耀 Android 真机验收，不以桌面尺寸模拟替代。
- 修复地图容器高度为零及隐藏实例继续渲染导致的 LngLat/Pixel NaN；校验坐标范围并明确提示缺失坐标，不修改历史计划。真机已显示实际高德底图和两个景点标记，反复触摸切换面板无页面异常。

- 行程页增加出发导航、按日切换、下一站、手动到访/跳过/撤销，以及景点、酒店、餐饮的高德入口。
- 步行和公交/地铁使用高德 URI API，默认起点为当前位置；支持相邻已知地点的固定起终点路线预览，不支持驾车、多日整单导入或自动到达判断。
- 仅将有效坐标且带高德 POI ID 的地点用于直接路线；未知来源坐标或缺失坐标使用城市、名称、地址搜索。入口位置须在高德确认。
- 进度保存在当前浏览器 localStorage，按计划、日期和地点序列隔离；不跨设备同步，不修改数据库、API 或历史行程。存储失败时提示仅本页有效。
- 提供显式网页备用链接、地址复制和微信浏览器提示；中英日韩文案同步。安卓 App 唤起需真机验收，桌面模拟不能替代。
- 验证：`cd frontend && npm test`、`npm run build`；手机验收需已安装高德，分别检查步行、公交、搜索备用、返回网页后的进度。手机外网访问需另行批准部署受保护 HTTPS，不使用电脑 loopback 地址。
- 部署仍需单独确认，仅更新 staging 前端；回滚恢复上一前端镜像即可，无数据库迁移，现有本地进度不影响旧版本。

## Phase 2 - 2026-08-07

- 增加 PostgreSQL、Redis、Celery 多服务运行架构。
- 增加 SQLAlchemy 2 模型和 Alembic 初始迁移。
- 将 legacy 与 V2 旅行规划任务改为数据库事实源。
- 将 legacy Planner 放入 Celery Worker 执行，未修改 Planner 文件。
- 增加 Redis Pub/Sub WebSocket、取消、重试、幂等和 Worker 恢复策略。
- 增加独立 staging volumes、基础设施 healthchecks 和真实依赖 CI。

## Phases 3–4 - 2026-08-08

- 保留 legacy Planner，并增加可切换的 JourneyGraph 类型化工作流和 PostgreSQL Checkpoint。
- 使用 Pydantic 结构化输出，不让主路径依赖括号修复或模型二次修 JSON。
- 增加 Web Research Provider、来源证据、官方来源排序、缓存 TTL 和结构化降级。
- 将小红书降为可选社区来源，Cookie 失效不再使整个规划失败。

## Phases 5–6 - 2026-08-08

- 增加出发地、城际交通、闭合时间轴、程序预算和六类确定性校验。
- 增加最多两轮的自动修订和仍未解决问题的显式展示。
- 增加持久 Human-in-the-loop、局部重规划、结构化 diff、不可变版本和追加式回滚。

## Phase 7 - 2026-08-08

- 增加 36 条固定旅行评测、legacy/JourneyGraph 对比和失败案例报告。
- 增加 trace、模型/Prompt/工具/工作流版本，以及 latency、token、cost、retry 和 cache_hit 遥测。
- 增加访问码、限流、输入/并发/模型预算和 Prompt Injection 基础防护。

## Phase 8 - 2026-08-08

- 前端切换到 API v2，增加完整约束输入、真实节点进度、失败重试和诊断 ID。
- 运行时设置接口改为浏览器安全状态，不再向匿名浏览器返回或允许修改服务端 Secret。
- 增加无 Key 的确定性 Demo 模式、独立 Compose、容器资源限制、日志轮转和非 root 运行。
- 增加 Caddy/Nginx HTTPS 示例、中英文项目入口、Before/After 架构、ADR 和演示脚本。

## Final DoD Audit - 2026-08-09

- 补齐规划中标准 `/api/v2/tasks/...`、Trip 资源、确认、重规划和反馈接口。
- 增加持久化、受限且不触发模型调用的用户反馈记录。
- 增加核心类型检查门禁，并保持 legacy Planner 文件不受检查改写。

GPL-2.0 License 和上游归属保持不变。
