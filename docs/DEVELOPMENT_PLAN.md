# TripStar 二次开发：编码 Agent 执行规划

> 项目暂定代号：**JourneyOps / TripStar Next**  
> 产品定位：从“一次性生成旅游攻略”升级为“有来源、可校验、可恢复、可动态重规划的旅行执行 Agent”。  
> 使用方式：把本文件放入仓库 `docs/DEVELOPMENT_PLAN.md`，再将下方“主开发 Agent 提示词”写入根目录 `AGENTS.md`。每次只让编码 Agent 完成一个阶段，验收后再进入下一阶段。

---

## 1. 项目最终目标

### 1.1 用户价值

用户输入出发地、目的地、日期、预算、节奏和偏好后，系统不仅生成行程，还需要：

1. 给出出发地到目的地、城市间和市内交通方案；
2. 对营业时间、闭馆日期、天气、活动、票价等时效信息提供来源和抓取时间；
3. 用确定性程序校验时间、路线、预算、营业时间和行程强度；
4. 在天气变化、景点关闭、交通延误或用户临时改变计划时，只重排受影响部分；
5. 保存任务状态和版本，服务或 Worker 重启后能够恢复；
6. 展示工具调用、来源、耗时、模型成本、校验问题和修改记录；
7. 通过自动化评测集证明改造前后效果，而不是只展示 UI。

### 1.2 求职展示目标

项目最终要能证明以下能力：

- Python / FastAPI 后端工程；
- LangGraph 状态图、Checkpoint、Memory、Human-in-the-loop；
- 结构化输出和 Tool Schema；
- MCP / 外部 API 工具集成；
- Redis + Celery 长任务、重试、幂等和状态同步；
- PostgreSQL、SQLAlchemy、Alembic；
- WebSocket 或 SSE 实时进度；
- Agent 可观测性、评测、失败分析与成本治理；
- Docker Compose、VPS 部署、CI/CD、日志和安全边界；
- 基于开源项目进行有边界、有归因的深度二次开发。

---

## 2. 项目范围

### 2.1 核心版本必须完成

- 原始 TripStar 功能可继续使用；
- `/api/v2` 新接口与旧接口并存；
- 新增明确的出发地和交通偏好；
- PostgreSQL 持久化 Trip、Task、Version、Source；
- Redis + Celery Worker；
- LangGraph 主工作流；
- Pydantic 结构化输出；
- 多来源旅行研究与引用；
- 确定性行程校验器；
- 动态重规划和版本差异；
- 基础评测集与评测报告；
- Docker Compose 多服务部署；
- README、架构图、改造说明和演示视频素材。

### 2.2 核心版本明确不做

- 不接入真实支付和自动购票；
- 不保存银行卡、身份证、护照等高敏感信息；
- 不承诺实时票务余量，除非使用合规且稳定的官方 API；
- 不先做完整多租户 SaaS；
- 不为了展示 RAG 强行建设大型景点向量库；
- 不一次性重写整个前端；
- 不把小红书抓取作为系统唯一数据源；
- 不编造“准确率 99.9%”或没有实验支持的指标。

### 2.3 可选增强项

- 用户旅行偏好长期记忆与 pgvector 语义检索；
- 日历导出；
- 邮件/Telegram/飞书行程提醒；
- 费用记账与计划预算对比；
- 多人协同行程；
- 中文和英文双语 README；
- 向原项目提交通用修复 PR。

---

## 3. 当前系统改造原则

1. **渐进迁移，不直接推倒重写。** 保留旧 Planner 作为 Baseline，通过 Feature Flag 切换新旧实现。
2. **先建立测试和契约，再改核心。** 先冻结旧 API 示例和前端所需 JSON，再开始拆分。
3. **LLM 负责理解与生成，程序负责计算与校验。** 预算求和、日期、距离、营业时间冲突不能依赖模型猜测。
4. **所有时效事实必须记录来源。** 至少保存 URL、标题、域名、抓取时间、事实类别和置信状态。
5. **所有外部调用必须可失败。** 统一超时、重试、错误分类、缓存和降级接口。
6. **所有长任务必须持久化。** API 进程不能成为任务唯一宿主。
7. **Agent 输出必须结构化。** 主流程不再依赖正则补括号和第二次模型修 JSON。
8. **先做单用户可靠版本。** 认证和多租户放在后续，不阻塞核心价值。
9. **生产环境与开发环境隔离。** VPS 当前服务只作为生产基线，开发使用 staging 域名、端口和独立数据卷。
10. **保留 GPL-2.0 许可证与上游归因。** README 明确列出基于 TripStar 的改造范围。

---

## 4. 目标架构

```text
                       ┌──────────────────────────────┐
                       │ Caddy / Nginx                │
                       │ HTTPS / Rate Limit / Routing │
                       └──────────────┬───────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
          ┌─────────▼─────────┐               ┌─────────▼──────────┐
          │ Vue 3 Frontend    │               │ FastAPI API         │
          │ Plan / Evidence   │◄────WS/SSE────│ /api/v2/trips      │
          │ Validation / Diff │               │ /replan /feedback   │
          └───────────────────┘               └───────┬────────────┘
                                                      │ create task
                                            ┌─────────▼──────────┐
                                            │ PostgreSQL          │
                                            │ Trips / Versions    │
                                            │ Tasks / Sources     │
                                            │ LangGraph Checkpoint│
                                            └─────────┬──────────┘
                                                      │
                                          ┌───────────▼───────────┐
                                          │ Redis                 │
                                          │ Broker / Cache / PubSub│
                                          └───────────┬───────────┘
                                                      │
                                            ┌─────────▼─────────┐
                                            │ Celery Worker      │
                                            │ invokes LangGraph  │
                                            └─────────┬─────────┘
                                                      │
                                     ┌────────────────▼────────────────┐
                                     │ LangGraph Orchestrator          │
                                     │ normalize → research → plan     │
                                     │ validate → revise → approval    │
                                     │ persist / replan                 │
                                     └────────┬───────────────┬────────┘
                                              │               │
                                  ┌───────────▼──────┐  ┌─────▼────────────┐
                                  │ Provider Adapters│  │ MCP Tool Adapters │
                                  │ Maps/Search/Weather│ │ custom/remote/local│
                                  └──────────────────┘  └──────────────────┘
```

### 4.1 推荐技术栈

- Frontend：Vue 3，尽量复用现有组件；
- API：FastAPI、Pydantic v2；
- Workflow：LangGraph；
- ORM：SQLAlchemy 2；
- Migration：Alembic；
- Database：PostgreSQL；
- Queue：Celery；
- Broker/Cache/Event：Redis；
- HTTP Client：httpx；
- Test：pytest、pytest-asyncio、respx；
- Lint/Format：ruff；
- Type Check：mypy 或 pyright，至少选择一个；
- Observability：结构化日志必做，LangSmith/Langfuse 以环境变量可选接入；
- Deployment：Docker Compose + Caddy/Nginx；
- CI：GitHub Actions。

---

## 5. 目标目录结构

```text
backend/app/
├── api/
│   ├── routes/                 # 保留 v1
│   └── v2/
│       ├── trips.py
│       ├── tasks.py
│       ├── replans.py
│       └── feedback.py
├── domain/
│   ├── trip_models.py
│   ├── source_models.py
│   ├── validation_models.py
│   └── task_models.py
├── agents/
│   ├── legacy/                 # 原 Planner 迁移到这里
│   └── journey_graph/
│       ├── state.py
│       ├── graph.py
│       ├── prompts.py
│       ├── nodes/
│       │   ├── normalize.py
│       │   ├── profile.py
│       │   ├── research.py
│       │   ├── maps.py
│       │   ├── transport.py
│       │   ├── draft.py
│       │   ├── validate.py
│       │   ├── revise.py
│       │   ├── approval.py
│       │   └── persist.py
│       └── replanning/
│           ├── graph.py
│           ├── impact.py
│           └── diff.py
├── tools/
│   ├── schemas.py
│   ├── registry.py
│   ├── map_tools.py
│   ├── weather_tools.py
│   ├── research_tools.py
│   └── transport_tools.py
├── providers/
│   ├── base.py
│   ├── amap.py
│   ├── google_maps.py
│   ├── web_search.py
│   ├── weather.py
│   └── xhs_optional.py
├── services/
│   ├── validation/
│   │   ├── itinerary_validator.py
│   │   ├── schedule_rules.py
│   │   ├── budget_rules.py
│   │   └── route_rules.py
│   ├── trip_service.py
│   ├── task_service.py
│   ├── source_service.py
│   └── event_service.py
├── repositories/
│   ├── trip_repository.py
│   ├── task_repository.py
│   └── source_repository.py
├── db/
│   ├── session.py
│   ├── orm_models.py
│   └── migrations/
├── workers/
│   ├── celery_app.py
│   └── trip_tasks.py
├── observability/
│   ├── logging.py
│   ├── metrics.py
│   └── tracing.py
├── evals/
│   ├── datasets/
│   ├── evaluators/
│   ├── run_eval.py
│   └── report.py
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── e2e/
```

---

## 6. 核心数据模型

### 6.1 TripRequestV2

建议字段：

```python
class TripRequestV2(BaseModel):
    origin: str
    destinations: list[CityStay]
    start_date: date
    end_date: date
    budget_total: Decimal | None
    currency: str = "CNY"
    travelers: int = 1

    transport_preferences: list[str] = []
    accommodation_preference: str | None = None
    interests: list[str] = []
    must_visit: list[str] = []
    avoid: list[str] = []

    pace: Literal["relaxed", "balanced", "intensive"] = "balanced"
    daily_start_time: time = time(9, 0)
    daily_end_time: time = time(21, 0)
    max_daily_walking_minutes: int | None = None
    accessibility_needs: list[str] = []

    free_text_input: str = ""
    language: str = "zh"
    timezone: str = "Asia/Shanghai"
```

约束：

- `end_date >= start_date`；
- 城市停留天数总和与日期跨度一致；
- 预算不得为负；
- 所有列表设置 `default_factory=list`，避免可变默认值；
- 输入长度有限制；
- 城市名、日期和时间统一标准化。

### 6.2 SourceEvidence

```python
class SourceEvidence(BaseModel):
    id: UUID
    title: str
    url: str
    domain: str
    provider: str
    claim_type: str
    claim_text: str
    published_at: datetime | None
    fetched_at: datetime
    freshness_status: Literal["fresh", "stale", "unknown"]
    trust_level: Literal["official", "major_platform", "community", "unknown"]
    confidence: float
```

### 6.3 ValidationIssue

```python
class ValidationIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "critical"]
    day_index: int | None
    item_id: str | None
    message: str
    evidence_ids: list[UUID] = []
    suggested_action: str | None
```

### 6.4 TripState

```python
class TripState(TypedDict, total=False):
    trip_id: str
    task_id: str
    request: TripRequestV2
    traveler_profile: dict

    research_queries: list[dict]
    sources: list[SourceEvidence]
    poi_candidates: dict[str, list[dict]]
    weather: dict[str, list[dict]]
    transport_options: list[dict]

    draft_plan: TripPlanV2 | None
    validation_report: ValidationReport | None
    revision_count: int
    approval_status: str
    final_plan: TripPlanV2 | None

    errors: list[dict]
    metrics: dict
```

---

## 7. LangGraph 主工作流

```text
START
  ↓
normalize_request
  ↓
load_profile
  ↓
prepare_research_queries
  ↓
┌────────────────────────────────────────────┐
│ parallel by destination                    │
│ research_web + search_pois + weather       │
└───────────────────┬────────────────────────┘
                    ↓
plan_intercity_transport
                    ↓
generate_draft_plan
                    ↓
deterministic_validate
                    ↓
       ┌──── critical issue? ────┐
       │ yes                      │ no
       ▼                          ▼
revise_plan ← max 2 loops     human_review_interrupt
       │                          │
       └──── validate again ──────┘
                                  ↓
                         persist_trip_version
                                  ↓
                                 END
```

### 7.1 节点职责

#### normalize_request

- 校验日期、城市、天数和预算；
- 标准化城市名、语言、时区；
- 生成幂等键；
- 不调用 LLM。

#### load_profile

- 获取用户历史偏好；
- 核心版本可只用结构化 JSON；
- 语义记忆属于可选增强。

#### prepare_research_queries

- 由 LLM 生成有限数量的研究问题；
- 输出结构化查询列表；
- 对“营业时间、闭馆、预约、活动、天气、签证”等时效问题设置优先级。

#### research_web

- 优先官方来源；
- 保存来源和抓取时间；
- API 失败时返回结构化错误，不让整个图崩溃；
- 小红书仅作为社区体验来源，不承担关键事实唯一证明。

#### search_pois / weather / transport

- 返回结构化对象；
- 不返回给 Agent 再解析的长文本；
- 每次调用记录 latency、provider、success、error_code、cache_hit。

#### generate_draft_plan

- 使用 Pydantic/JSON Schema 结构化输出；
- 模型只负责组合和解释；
- 预算合计由程序后处理；
- 不允许模型编造具体车次、库存或实时票价。

#### deterministic_validate

- 运行全部规则；
- 生成 `ValidationReport`；
- critical 问题必须进入修订；
- warning 可交给用户决定。

#### revise_plan

- 输入仅包含原计划、结构化问题和必要来源；
- 每次只修改存在问题的部分；
- 最多两轮，防止无限循环；
- 超过上限则保留问题并提示用户。

#### human_review_interrupt

- 用户可确认、修改要求或拒绝；
- 保存 Checkpoint；
- 用户回来后从该节点继续。

#### persist_trip_version

- 保存最终计划、来源、校验结果、模型和 Prompt 版本；
- 版本号递增；
- 生成前后差异摘要。

---

## 8. 动态重规划工作流

### 8.1 触发条件

- 用户主动说“今天下雨，把户外项目换掉”；
- 某景点关闭或预约失败；
- 交通延误；
- 用户晚起、身体不适或预算变化；
- 用户临时增加/删除景点。

### 8.2 ReplanState

```python
class ReplanState(TypedDict, total=False):
    trip_id: str
    base_version: int
    change_request: TripChangeRequest
    current_plan: TripPlanV2
    impacted_item_ids: list[str]
    fresh_sources: list[SourceEvidence]
    replacement_candidates: list[dict]
    proposed_plan: TripPlanV2
    validation_report: ValidationReport
    diff: TripPlanDiff
    approval_status: str
```

### 8.3 工作流

```text
change_request
  ↓
identify_impacted_scope
  ↓
refresh_only_required_data
  ↓
find_replacements
  ↓
patch_affected_day_or_items
  ↓
validate
  ↓
generate_human_readable_diff
  ↓
human approval
  ↓
persist new version
```

验收重点：

- 不允许因为一天下雨重写全部行程；
- 未受影响的 item_id 保持不变；
- 前端明确展示删除、移动、新增和原因；
- 新计划必须再次经过校验。

---

## 9. 确定性校验器规则

### 9.1 结构与日期

- 每一天日期连续；
- 天数与请求一致；
- 每天 city 正确；
- 城市切换日明确；
- item_id 唯一；
- 没有重复景点。

### 9.2 时间可行性

- 每个项目有开始、结束或持续时间；
- 通勤时间计入日程；
- 不超过用户每日起止时间；
- 吃饭和入住时间合理；
- 交通日不安排过量景点；
- 营业时间和闭馆日冲突标为 critical。

### 9.3 路线可行性

- 相邻地点有路线或距离数据；
- 单日总通勤时间不超过阈值；
- 明显往返折返给 warning；
- 步行强度超过用户阈值给 warning/critical；
- 缺坐标时不能伪造坐标，标记数据缺失。

### 9.4 预算

- 每项费用为 Decimal；
- 总预算由程序求和；
- 分项和总计一致；
- 超预算给 critical 或 warning；
- 不确定费用标记区间与来源，不伪装成精确值。

### 9.5 天气与场景

- 大雨、高温等条件下户外长时间活动给 warning；
- 室内备选方案必须可查询；
- 天气日期不在 API 预报范围时标记“历史气候/未知”，不能冒充实时预报。

---

## 10. 外部工具和 Provider 设计

### 10.1 统一接口

```python
class MapProvider(Protocol):
    async def search_pois(...): ...
    async def get_place_details(...): ...
    async def route_matrix(...): ...

class WeatherProvider(Protocol):
    async def forecast(...): ...

class WebResearchProvider(Protocol):
    async def search(...): ...
    async def research(...): ...

class TransportProvider(Protocol):
    async def compare_intercity_options(...): ...
```

### 10.2 MCP 使用边界

- 当前已有 MCP 能力，不把“用了 MCP”当作唯一改造点；
- 内部业务代码依赖统一 Tool Schema，不直接依赖某一个 MCP Server；
- MCP Server、原生 SDK 和 REST API 都通过 Adapter 接入；
- 工具输入输出必须有 Schema；
- 工具调用设置权限、超时、速率限制和日志；
- 读取类工具可以自动调用；
- 涉及预订、支付、发送消息等写操作必须人工确认；
- 对外部 MCP Server 采用允许列表，禁止任意命令执行。

### 10.3 小红书策略

- 设置 `XHS_ENABLED=false` 为可选默认；
- Cookie 不写日志、不进入错误响应；
- 失败只影响社区内容，不阻塞主计划；
- 官方事实优先官方来源；
- 图片可改为地图/官方/占位图降级；
- 保留原功能但明确风险和数据来源性质。

---

## 11. 长任务、队列和恢复设计

### 11.1 API 提交

1. API 验证请求；
2. 写入 `trip_tasks`；
3. 生成 `task_id`、`trip_id`、`idempotency_key`；
4. Celery `delay(task_id)`；
5. 立即返回 202；
6. 前端通过 WebSocket/SSE 获取进度。

### 11.2 Worker

- 从数据库读取请求；
- 使用 `thread_id=trip_id` 调用 LangGraph；
- 节点边界保存 Checkpoint；
- 进度事件写 Redis Pub/Sub 和数据库；
- 可重试错误使用指数退避；
- 不可重试错误立即失败并保存诊断；
- 每个任务有最大运行时间；
- 同一 trip 的重规划加分布式锁。

### 11.3 错误分类

```text
RETRIABLE
- 网络超时
- 429 限流
- 临时 5xx
- Redis/Postgres 短暂连接错误

NON_RETRIABLE
- 请求 Schema 错误
- API Key 未配置
- 权限拒绝
- 模型持续违反结构化输出
- 不支持的城市/日期范围

PARTIAL
- 一个来源失败，但仍有其他来源
- 图片失败
- 社区内容失败
```

### 11.4 幂等

- 同一个请求短时间重复提交返回已有任务；
- 节点写数据库采用 upsert；
- Source 通过 URL + fetched_at bucket 去重；
- Celery 重投不能生成重复版本；
- 每次持久化版本需唯一约束 `(trip_id, version)`。

---

## 12. 数据库建议

### 12.1 表

- `traveler_profiles`
- `trips`
- `trip_tasks`
- `trip_versions`
- `source_evidence`
- `trip_source_links`
- `tool_call_logs`
- `user_feedback`
- LangGraph Checkpoint 所需表

### 12.2 存储策略

- TripPlan 使用 JSONB，避免早期过度拆表；
- 用独立列保存 `origin`、`start_date`、`end_date`、`status` 方便查询；
- Source 单独存储，便于复用和审计；
- 原始网页不长期完整存储，保存必要摘要和元数据；
- 日志不保存 API Key、Cookie 和高敏感信息。

---

## 13. API v2 契约

```text
POST   /api/v2/trips
GET    /api/v2/trips/{trip_id}
GET    /api/v2/trips/{trip_id}/versions
GET    /api/v2/trips/{trip_id}/versions/{version}
POST   /api/v2/trips/{trip_id}/approve
POST   /api/v2/trips/{trip_id}/replan
GET    /api/v2/tasks/{task_id}
GET    /api/v2/tasks/{task_id}/events
WS     /api/v2/tasks/{task_id}/ws
POST   /api/v2/trips/{trip_id}/feedback
```

### 13.1 兼容策略

- 不删除 `/api/trip/plan`；
- 增加 `PLANNER_ENGINE=legacy|journey_graph`；
- v2 结果提供到旧 `TripPlan` 的 Adapter；
- 前端先只增加新字段和来源/校验卡片；
- 新流程稳定后再逐步减少旧代码。

---

## 14. 分阶段开发任务

## 阶段 0：基线审计、备份与生产隔离

### 目标

确保当前 VPS 版本可恢复，建立开发和 staging 边界。

### Agent 任务

1. 只读检查仓库结构、Dockerfile、Compose、环境变量、启动流程和数据卷；
2. 输出 `docs/BASELINE_AUDIT.md`；
3. 输出当前 API 列表、数据模型、主流程和风险；
4. 记录一次真实成功任务和一次失败任务；
5. 保存旧接口响应样例到 `tests/fixtures/legacy/`；
6. 增加 `/health/live`、`/health/ready`；
7. 创建 `staging` Compose override；
8. 编写备份和恢复说明；
9. 不修改主业务逻辑。

### 验收

- 当前版本可一键重新部署；
- 数据卷和 `.env` 有备份方案；
- staging 与 production 使用不同端口/域名/数据卷；
- 有 Baseline 响应、耗时和失败记录；
- `docker compose config` 通过；
- 健康检查可用。

### 推荐提交

`chore: establish baseline audit, health checks and staging isolation`

---

## 阶段 1：测试地基、领域模型与 API v2 骨架

### 目标

先建立规范驱动开发地基，不迁移 Agent。

### Agent 任务

1. 增加 pytest、pytest-asyncio、respx、ruff；
2. 写旧接口 Contract Test；
3. 新建 `domain/` 中的 v2 Pydantic 模型；
4. 修复所有可变默认列表；
5. 新增 `/api/v2/trips`，先返回 mock task record，但不调用模型；
6. 增加统一错误响应；
7. 建立 `docs/API_V2.md` 和 OpenAPI 示例；
8. GitHub Actions 运行 lint、test、frontend build。

### 验收

- 旧接口合同测试通过；
- v2 Schema 能拒绝日期、天数、预算等非法输入；
- OpenAPI 页面可查看完整示例；
- CI 通过；
- 业务逻辑仍走 legacy。

### 推荐提交

`test: add contract tests and v2 domain schemas`

---

## 阶段 2：PostgreSQL、Redis、Celery 与持久任务

### 目标

解决 API 进程重启导致任务丢失的问题。

### Agent 任务

1. 增加 PostgreSQL、Redis、Celery 服务；
2. 引入 SQLAlchemy 2 和 Alembic；
3. 建立 `trips`、`trip_tasks`、`trip_versions` 基础表；
4. API 创建任务后写数据库并投递 Worker；
5. Worker 暂时仍调用 legacy Planner；
6. 将进度写数据库，并通过 Redis Pub/Sub 推送；
7. WebSocket 从 Pub/Sub 读取，不再依赖 API 内存 Queue；
8. 增加任务取消、重试和幂等；
9. 编写 Worker 重启和 API 重启集成测试；
10. 数据库、Redis、Worker 增加 healthcheck。

### 验收

- 重启 API 不影响正在运行的任务；
- Worker 被终止后任务能够按策略恢复或明确失败；
- 两个 API 实例可以查询同一任务；
- 重复请求不产生重复版本；
- legacy Planner 在新队列架构上可运行；
- 不再把 JSON 文件和进程内字典作为任务事实来源。

### 推荐提交

`feat: add durable task execution with postgres redis and celery`

---

## 阶段 3：LangGraph 骨架与结构化输出

### 目标

将单体 Planner 渐进迁移为可恢复的状态图。

### Agent 任务

1. 将旧 Planner 移入 `agents/legacy/`，保持行为；
2. 新建 LangGraph State 和节点接口；
3. 首批实现 `normalize → collect → draft → validate_stub → persist`；
4. 接入 Postgres Checkpointer；
5. 使用模型原生或 ToolStrategy 结构化输出到 `TripPlanV2`；
6. 工具返回对象，不返回需要模型二次解析的长字符串；
7. 主路径不调用 `_sanitize_json_str`、括号修复或 `_llm_repair_json`；
8. 保留 `LEGACY_JSON_REPAIR=true` 仅作为临时降级；
9. 通过 Feature Flag 对同一请求运行 legacy 和 graph；
10. 保存两个版本输出用于对比。

### 验收

- 图可视化文件生成；
- 每个节点独立测试；
- Checkpoint 能查看和恢复；
- 30 次结构化输出测试中没有未捕获 JSON Parse Error；
- legacy 与 graph 均可切换；
- graph 输出能被现有前端 Adapter 消费。

### 推荐提交

`feat: introduce langgraph workflow and typed trip output`

---

## 阶段 4：来源化旅行研究与 Provider 降级

### 目标

解决地图之外的实时信息缺口，并降低对小红书单一来源的依赖。

### Agent 任务

1. 定义 `WebResearchProvider`；
2. 至少实现一个联网搜索 Provider，并保留 Noop/Fallback；
3. 设计官方来源优先排序；
4. 每个事实保存 SourceEvidence；
5. 为营业时间、闭馆、预约、活动、旅行提示生成查询；
6. 对 401、429、超时、空结果和异常 JSON 写测试；
7. 小红书改为 Optional Community Provider；
8. 关键事实没有来源时标记 unknown；
9. 前端增加“来源与更新时间”卡片；
10. 增加来源缓存 TTL。

### 验收

- 关键时效信息可以追溯到来源；
- 未配置搜索 Key 时系统仍能生成降级计划；
- 小红书 Cookie 失效不使整个任务失败；
- Key 和 Cookie 不出现在日志、响应和 Trace；
- 单个 Provider 故障不会导致全局失败；
- UI 能查看来源和抓取时间。

### 推荐提交

`feat: add source-backed travel research with provider fallbacks`

---

## 阶段 5：出发地、交通规划与确定性校验器

### 目标

把项目从“目的地景点拼接”升级为端到端可执行行程。

### Agent 任务

1. 前后端增加 `origin`；
2. 增加城际交通方案模型；
3. 接入可用的路线/距离矩阵能力；
4. 给每日项目增加 start/end/duration/item_id；
5. 实现日期、时间、路线、预算、营业时间和强度校验；
6. 程序重新计算预算；
7. 校验结果进入 revise 节点；
8. 最多修订两轮；
9. 前端展示 critical/warning/info；
10. 增加“为什么这样安排”的解释。

### 验收

- 出发地到目的地存在明确交通建议；
- 每天时间轴闭合；
- 预算字段由程序计算且分项一致；
- 闭馆冲突能被自动发现；
- 路线明显不可行能被发现；
- 最终计划无 critical 问题，或明确告知仍存在的问题；
- 模型不能写入虚构的车次和实时余票。

### 推荐提交

`feat: add origin transport planning and deterministic itinerary validation`

---

## 阶段 6：Human-in-the-loop 与动态重规划

### 目标

实现真正有状态、可交互的旅行执行 Agent。

### Agent 任务

1. 在初版计划后加入 interrupt；
2. 支持确认、修改和拒绝；
3. 新建 Replan Graph；
4. 实现影响范围识别；
5. 只刷新必要数据；
6. 生成结构化 diff；
7. 用户确认后保存新版本；
8. 增加版本回滚；
9. 前端增加版本和差异视图；
10. 写服务重启后继续人工审核的测试。

### 验收

- 用户离开页面后可以继续审核；
- 服务重启后 Checkpoint 仍可恢复；
- 局部变化不会重写全行程；
- 新旧版本可比较和回滚；
- 每次重排记录原因、来源和校验结果。

### 推荐提交

`feat: add human approval and scoped dynamic replanning`

---

## 阶段 7：评测、可观测性、安全和成本治理

### 目标

让项目从“能跑”变成“可证明、可诊断、可运营”。

### Agent 任务

1. 建立 30 条以上真实旅行评测数据；
2. 实现代码 Evaluator；
3. 记录模型、Prompt、工具和工作流版本；
4. 记录 token、费用、latency、retry、cache_hit；
5. 可选接入 LangSmith/Langfuse；
6. 增加 trace_id/task_id/trip_id；
7. 增加 API Rate Limit 和访问码；
8. 限制输入长度、并发和模型预算；
9. 增加 Prompt Injection 基础防护；
10. 生成 `docs/EVALUATION_REPORT.md`。

### 验收

- 每次实验可以复现；
- 可以比较 legacy 与 graph；
- 可以定位某个失败发生在哪个节点、哪个工具；
- 有离线回归测试；
- 公开 VPS 不会被匿名用户无限消耗模型额度；
- 日志中无 Secret；
- 评测报告包含失败案例，不只展示成功案例。

### 推荐提交

`feat: add agent evaluation observability and production guardrails`

---

## 阶段 8：产品界面、发布和作品集包装

### 目标

形成招聘者可以运行、理解和验证的完整项目。

### Agent 任务

1. 优化输入表单：出发地、预算、节奏、每日时间、步行限制；
2. 结果页增加来源、校验、交通、版本和 diff；
3. loading 页面展示真实节点进度；
4. 增加失败恢复按钮和错误诊断 ID；
5. 完善 Docker Compose、健康检查和备份；
6. 增加 Caddy/Nginx HTTPS 配置示例；
7. 编写 README 中英文版本；
8. 编写 `CHANGELOG_FROM_UPSTREAM.md`；
9. 编写架构决策记录 ADR；
10. 准备演示脚本、截图和 release tag。

### 验收

- 新环境按照 README 可以启动；
- 无 Key 时有 Demo/Mock 模式；
- 有 Before/After 架构图；
- 有实际评测指标；
- 有 3 到 5 分钟演示流程；
- README 明确原项目归因和许可证；
- GitHub 首页能在一分钟内让招聘者理解项目价值。

### 推荐提交

`docs: package journeyops release with demo evaluation and attribution`

---

## 15. 评测集设计

### 15.1 用自己的真实旅行经历构建样例

至少包含：

- 南宁出发到桂林，多日公共交通；
- 当天中午才到达；
- 下雨替换户外项目；
- 博物馆周一闭馆；
- 预算 1000 元；
- 每天步行不超过 15000 步或指定分钟；
- 慢节奏，一个人旅行；
- 临时取消一个景点；
- 换酒店；
- 多城市切换；
- 海外城市和时区；
- 搜索 API 429；
- 地图 API 超时；
- 小红书 Cookie 失效；
- Worker 运行中重启；
- 用户审核后隔天回来继续。

### 15.2 代码评测指标

- Schema Valid Rate；
- Date Consistency；
- Budget Arithmetic Correctness；
- Critical Conflict Count；
- Duplicate POI Count；
- Source Coverage；
- Freshness Coverage；
- Tool Success Rate；
- Retry Recovery Rate；
- Resume Success Rate；
- Replan Scope Precision；
- End-to-end Latency；
- Model Cost per Trip。

### 15.3 建议目标

这些是验收目标，不得在完成实验前写进简历：

- 结构化输出通过率 ≥ 98%；
- 预算计算正确率 100%；
- 日期一致性 100%；
- 最终计划 critical 冲突清零率 ≥ 90%；
- 时效性关键事实来源覆盖率 ≥ 80%；
- API 进程重启后的任务查询成功率 100%；
- 审核节点恢复成功率 100%；
- 动态重规划保留未受影响项目比例 ≥ 90%。

---

## 16. VPS 部署与安全清单

### 16.1 开发前

- 备份仓库 commit hash；
- 备份 `.env`，但不要提交；
- 备份现有 Docker volume；
- 记录域名、端口、反向代理和防火墙；
- 导出一次当前可用的完整响应；
- 创建 staging 域名或端口；
- staging 使用独立 Redis、Postgres 和 Volume。

### 16.2 Compose 服务

```text
caddy/nginx
frontend
api
worker
redis
postgres
```

每个服务：

- healthcheck；
- restart policy；
- 日志轮转；
- CPU/内存边界；
- 非 root 用户；
- secrets 通过 env/file 注入；
- 持久卷明确命名；
- 数据库每日备份和恢复演练。

### 16.3 对公网开放前

- HTTPS；
- CORS 白名单；
- 访问码或用户认证；
- IP/用户级限流；
- 模型调用单日预算；
- 请求体长度限制；
- 禁止任意 URL SSRF；
- MCP Server 允许列表；
- 禁止任意文件和命令工具；
- 日志脱敏；
- `/docs` 可在生产关闭或加认证。

---

## 17. Git 和文档规范

### 17.1 分支

```text
main                 # 稳定公开版本
staging              # VPS staging
feat/task-runtime
feat/langgraph-core
feat/research-evidence
feat/validator
feat/replanning
```

### 17.2 每阶段输出

- 代码；
- 测试；
- 文档；
- Migration；
- OpenAPI 变化；
- 部署变化；
- 风险和回滚方式；
- 一次独立 commit。

### 17.3 必备文档

```text
docs/BASELINE_AUDIT.md
docs/ARCHITECTURE.md
docs/API_V2.md
docs/DEVELOPMENT_PLAN.md
docs/EVALUATION_REPORT.md
docs/DEPLOYMENT.md
docs/SECURITY.md
docs/CHANGELOG_FROM_UPSTREAM.md
docs/adr/0001-*.md
```

---

## 18. 主开发 Agent 提示词

将以下内容放入仓库根目录 `AGENTS.md`，或作为新会话第一条提示词：

```text
你是 TripStar 二次开发项目的主开发 Agent。你的任务不是简单改名、换 UI 或堆砌框架，而是将现有 TripStar 渐进重构为一个“有来源、可校验、可恢复、可动态重规划”的旅行执行 Agent。

项目原则：
1. 先阅读 README、LICENSE、Dockerfile、docker-compose.yaml、backend/app、frontend/src 和 docs/DEVELOPMENT_PLAN.md。
2. 当前 VPS 已有可用版本。严禁直接在生产环境试验；所有改动先在 staging 分支和独立数据卷完成。
3. 不推倒重写。旧 API 和 legacy Planner 必须保留，使用 Feature Flag 渐进迁移。
4. 每次只执行 DEVELOPMENT_PLAN 中的一个阶段。开始编码前，先输出：现状、目标、拟修改文件、数据库/API 影响、测试方案、回滚方案。
5. 未经测试不得宣称完成。每个阶段必须包含单元测试、必要的集成测试、文档和独立 commit。
6. LLM 只负责理解、研究和生成；日期、预算、距离、时间冲突、营业时间校验由确定性代码处理。
7. 所有 LLM 最终输出使用 Pydantic/JSON Schema 结构化输出。不得把正则修 JSON 作为主路径。
8. 所有外部工具返回结构化对象；统一处理 timeout、429、5xx、空结果和无 Key；单个 Provider 失败不得导致不必要的全局失败。
9. 所有时效事实保存来源 URL、标题、域名、抓取时间和可信级别。没有来源时标记 unknown，禁止编造。
10. XHS_COOKIE、API Key、数据库密码等 Secret 不得写入日志、测试快照、错误响应、Git 或 Trace。
11. 长任务必须通过持久队列执行，状态写数据库；API 进程内内存不得作为唯一事实来源。
12. 所有任务和节点应具备幂等性；Worker 重试不能产生重复 Trip Version。
13. 涉及付费、预订、发送、写入外部系统等操作必须设置 Human-in-the-loop，不允许自动执行。
14. 保留 GPL-2.0 LICENSE、原作者归因，并维护 CHANGELOG_FROM_UPSTREAM.md。
15. 不伪造性能、准确率、用户量或业务指标。所有简历指标必须来自 eval 或日志。
16. 不擅自扩展 MVP 范围。发现新想法写入 backlog，不阻塞当前阶段。

每次任务结束必须输出：
- 完成的功能；
- 变更文件；
- 数据库/API 变化；
- 执行过的命令和测试结果；
- 已知问题；
- 部署/回滚步骤；
- 下一阶段建议，但不要自行开始下一阶段。
```

---

## 19. 交给 Agent 的第一条执行指令

```text
现在只执行《TripStar 二次开发：编码 Agent 执行规划》的“阶段 0：基线审计、备份与生产隔离”。

约束：
- 先只读检查，不直接修改核心业务代码；
- 不删除、移动或重写 trip_planner_agent.py；
- 不更换框架；
- 不修改生产数据；
- 不输出或提交任何 Secret；
- 先报告仓库真实现状，不能依据规划文档假设文件已经存在。

必须交付：
1. docs/BASELINE_AUDIT.md；
2. 当前系统 Mermaid 架构图；
3. API、任务状态、数据存储和外部依赖清单；
4. 风险按 P0/P1/P2 排序；
5. tests/fixtures/legacy 下至少一个成功响应和一个失败响应的脱敏 fixture；
6. /health/live 与 /health/ready；
7. staging compose override 示例；
8. docs/DEPLOYMENT.md 中的备份、恢复和回滚步骤；
9. 对本阶段执行测试并报告结果；
10. 一个独立 commit，不开始阶段 1。
```

---

## 20. 项目完成后的 README 首页结构

1. 一句话产品定位；
2. 在线 Demo；
3. 30 秒 GIF/视频；
4. “为什么做”：毕业旅行的真实痛点；
5. 与原 TripStar 的区别；
6. Before/After 架构；
7. LangGraph 工作流图；
8. 核心功能；
9. 评测结果；
10. 失败恢复演示；
11. 动态重规划演示；
12. 本地启动；
13. VPS 部署；
14. 安全和成本说明；
15. Roadmap；
16. 上游归因与 GPL-2.0。

---

## 21. 简历表达模板

只有实际完成和测量后再填写数字：

> 基于 GPL-2.0 开源项目 TripStar 进行产品与架构重构，面向本人毕业旅行中遇到的实时闭馆、天气变化、交通衔接和路线不可行问题，将一次性攻略生成升级为可恢复、可校验、可动态重规划的旅行执行 Agent。

> 使用 LangGraph 编排旅行研究、地图/天气工具、交通规划、行程生成、确定性校验、Human-in-the-loop 和局部重规划节点；基于 PostgreSQL Checkpoint、Redis 与 Celery 实现长任务持久化、失败重试及服务重启恢复。

> 构建 XX 条真实旅行评测集，结构化输出通过率由 XX% 提升至 XX%，最终行程 critical 冲突降低 XX%，时效信息来源覆盖率达到 XX%；通过工具调用日志监控任务成功率、延迟和模型成本。

---

## 22. 最终 Definition of Done

项目只有同时满足以下条件才算完成：

- [ ] 原始功能仍可通过 legacy 模式运行；
- [ ] 新版 LangGraph 流程可运行；
- [ ] 任务不依赖 API 进程内内存；
- [ ] 服务重启后可查询、恢复或明确处理任务；
- [ ] 结构化输出为主路径；
- [ ] 关键时效事实有来源；
- [ ] 出发地和交通纳入行程；
- [ ] 有确定性校验器；
- [ ] 有动态重规划和版本差异；
- [ ] 有 Human-in-the-loop；
- [ ] 有至少 30 条评测数据；
- [ ] 有自动化回归评测；
- [ ] 有日志、Trace、耗时和成本数据；
- [ ] 有基础安全和限流；
- [ ] 有 Docker Compose 多服务部署；
- [ ] 有 CI；
- [ ] 有完整 README 和演示材料；
- [ ] 有上游归因和许可证；
- [ ] 所有简历指标均能由测试或日志复现。
