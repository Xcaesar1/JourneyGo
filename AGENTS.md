# JourneyOps Project Instructions

本仓库把上游 TripStar 渐进改造为有来源、可校验、可恢复、可动态重规划的旅行执行 Agent。
`docs/DEVELOPMENT_PLAN.md` 是阶段、范围和 Definition of Done 的权威规范。

## 开始工作前

1. 阅读 `README.md`、`LICENSE`、`Dockerfile`、`docker-compose.yaml`、`backend/app`、
   `frontend/src` 和 `docs/DEVELOPMENT_PLAN.md`。
2. 用当前工作树、Git 历史、测试、CI 和实际部署状态判断当前阶段；不得把规划中的文件或能力
   当作已经存在。
3. 开始编码前说明现状、目标、拟修改文件、数据库/API 影响、测试方案和回滚方案。
4. 每次只执行一个阶段；阶段已结束时，只补该阶段或最终 Definition of Done 的可证明缺口，
   不自行扩展 MVP。

## 工程边界

1. 生产环境只作为基线。所有试验先在 `staging` 分支、loopback 端口和独立 PostgreSQL、Redis、
   应用数据卷中完成；未经明确批准不得提升生产、迁移生产数据或修改 Caddy/DNS。
2. 不推倒重写。保留旧 API 和 `backend/app/agents/legacy/trip_planner_agent.py`，通过
   `PLANNER_ENGINE` 渐进切换；不得删除、移动或重写 legacy Planner。
3. LLM 只负责理解、研究和生成。日期、预算、距离、时间冲突、营业时间和强度由确定性代码处理。
4. LLM 主路径必须使用 Pydantic/JSON Schema 结构化输出，不得依赖正则或二次模型修复 JSON。
5. 外部 Provider 返回结构化对象，并统一处理无 Key、timeout、429、5xx、空结果和降级；单个
   Provider 失败不得导致不必要的全局失败。
6. 时效事实保存来源 URL、标题、域名、抓取时间和可信级别；没有来源时标记 `unknown`，禁止编造。
7. API Key、Cookie、访问码、数据库密码等 Secret 不得进入 Git、日志、错误响应、测试 Fixture
   或 Trace。示例只能使用明显虚假的占位值。
8. 长任务通过 PostgreSQL、Redis 和 Celery 执行；API 内存不得作为唯一事实源。任务和节点保持
   幂等，Worker 重试不得生成重复 Trip Version。
9. 预订、支付、发送消息和写入外部系统必须经过 Human-in-the-loop，不得自动执行。
10. 保留 GPL-2.0 LICENSE、上游归因和 `docs/CHANGELOG_FROM_UPSTREAM.md`。
11. 不伪造性能、准确率、用户量或业务指标；README 和简历数字必须能由固定评测、测试或日志复现。

## 验证与 Git

1. 未实际测试不得宣称完成。功能应包含单元测试、必要的集成测试、文档、Migration/OpenAPI/部署
   变化和回滚说明。
2. 每跑通一个独立功能就创建一次独立 commit，便于逐项回滚和维护；不要把多个无关功能压进
   同一提交，不要 amend 已有提交。
3. 提交前检查工作区和 Secret，禁止覆盖用户或其他 Agent 的无关修改。
4. 每次任务结束报告完成内容、变更文件、数据库/API 变化、测试结果、已知问题、部署/回滚步骤和
   下一步；不得在未经授权时自动开始下一阶段。
