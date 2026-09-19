# API Key 配置指南

## 放在哪里

- Docker 部署：复制根目录 `.env.staging.example` 为 `.env.staging`，用 `docker compose --env-file .env.staging ...` 加载。
- 本地后端：复制 `backend/.env.example` 为 `backend/.env`，从后端目录启动，或在仓库根目录启动前显式加载其中环境变量。
- 前端开发：`frontend/.env` 只放 API 地址与浏览器地图 Key。不要把模型、酒店、航班等服务端密钥写进任何 `VITE_*` 前端变量。
- Demo：使用 `.env.demo.example`，不需要任何供应商 Key。
- 下文 `replace-with-*` 均为占位文字，不能用于真实请求。模板默认留空的 Key 不表示功能已配置。

## 按功能准备

| 功能 | 环境变量 | 是否需要 | 配置来源与说明 |
| --- | --- | --- | --- |
| 模型规划 | `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_ID` | 真实模型规划需要 | 自己的模型服务控制台；Key、接口地址和模型名称必须属于同一服务。 |
| 地点、公交及驾车路线 | `VITE_AMAP_WEB_KEY` | 真实高德查询需要 | 高德开放平台应用的 **Web 服务** Key。变量虽带 VITE 前缀，此值只放后端环境。 |
| 页面地图 | `VITE_AMAP_WEB_JS_KEY`、`VITE_AMAP_SECURITY_JS_CODE` | 显示高德 JS 地图需要 | 高德开放平台 **Web端(JS API)** Key 及对应安全码；设置站点域名限制。 |
| 整趟专属地图 | 复用高德服务 Key，另设 `AMAP_PERSONAL_MAP_ENABLED=true` | 按需启用 | 核实账户的 MCP / 专属地图权限与配额，并经用户确认后创建；不是额外的通用 API Key 字段。 |
| 高铁查询 | 无独立 Key；`TRAVEL_TRAIN_ENABLED=true` | 按需启用 | 当前 12306 MCP 适配器无需项目 API Key；仍需可用网络和正确桥接依赖。 |
| 酒店查询 | `ROLLINGGO_API_KEY` | 酒店功能需要 | 自己的 RollingGo 账户凭据，同时启用 `TRAVEL_HOTEL_ENABLED`。 |
| 航班查询 | `VARIFLIGHT_API_KEY` | 飞机功能需要 | 自己的飞常准账户凭据；还需访问码、显式付费确认和累计调用上限。 |
| 天气 | 无独立 Key；`WEATHER_ENABLED=true` | 按需启用 | 当前 Open-Meteo 公共接口适配路径，不使用 Key；使用范围见 `WEATHER.md`。 |
| 联网研究 | `BRAVE_SEARCH_API_KEY` | 可选 | Brave Search 服务凭据，不是最小 Demo 的前置条件。 |
| 携程问道补充资料 | `TRIPAI_API_KEY`、`TRIPAI_ENABLED=true` | 可选 | 自己的问道服务权限与凭据。 |
| Google 地图后端能力 | `GOOGLE_MAPS_API_KEY` | 可选 | 自己的 Google Cloud 项目 Key；不是国内高德流程必填项。 |

当前配置中的 `XHS_COOKIE` / `XHS_ENABLED` 是停用的兼容字段，新部署不需要准备或提交小红书 Cookie。

## 高铁 + 酒店 + 高德示例

以下仅展示需要修改的变量，数据库、队列和超时等其余配置继续使用完整模板。不要将示例作为包含真实凭据的文件提交。

```dotenv
DEMO_MODE=false
PLANNER_ENGINE=journey_graph
LLM_API_KEY=replace-with-your-model-api-key
LLM_BASE_URL=https://your-model-provider.example/v1
LLM_MODEL_ID=your-model-id

VITE_AMAP_WEB_KEY=replace-with-amap-web-service-key
VITE_AMAP_WEB_JS_KEY=replace-with-amap-browser-js-key
VITE_AMAP_SECURITY_JS_CODE=replace-with-amap-browser-security-code

ONE_CLICK_TRAVEL_ENABLED=true
TRAVEL_TRAIN_ENABLED=true
TRAVEL_HOTEL_ENABLED=true
ROLLINGGO_API_KEY=replace-with-rollinggo-hotel-key
WEATHER_ENABLED=true

API_ACCESS_CODE_REQUIRED=true
API_ACCESS_CODE=replace-with-your-random-access-code
POSTGRES_PASSWORD=replace-with-your-random-database-password

# 未获得地图创建授权前保持关闭。
AMAP_PERSONAL_MAP_ENABLED=false
# 未明确批准付费查询前保持关闭。
TRAVEL_FLIGHT_ENABLED=false
VARIFLIGHT_API_KEY=
TRAVEL_FLIGHT_CALL_LIMIT=0
```

## 飞机能力单独启用

确认账户费用和授权后，再在私有配置中填写以下变量。`15` 是累计调用次数的**示例**，不是余额、每日额度或默认免费次数；已有环境必须保留原计数，不能通过改名或清理 Redis 重新获得额度。

```dotenv
TRAVEL_FLIGHT_ENABLED=true
VARIFLIGHT_API_KEY=replace-with-variflight-key
TRAVEL_FLIGHT_CALL_LIMIT=15
API_ACCESS_CODE_REQUIRED=true
API_ACCESS_CODE=replace-with-your-random-access-code
```

一般一次未缓存的往返查询会调用两次。开启功能并不等于立即查询，用户提交时仍需确认付费授权。示例不会替你修改运行中配置。

## 密钥与密码的区别

- `API_ACCESS_CODE` 是自己生成的接口访问码，不向第三方购买；前端通过请求头提供，接口不会回显它。
- `POSTGRES_PASSWORD` 是自己设置的数据库密码，不是供应商 API Key。使用随机 URL-safe 值，避免连接字符串中的特殊字符歧义。
- 高德 Web JS Key 和安全码当前会提供给浏览器地图 SDK，不能视为浏览器不可见秘密；应限制域名。Web 服务 Key、模型和付费服务凭据不应返回浏览器。
- 不要把 Key 写进 README、截图、错误日志、公开 Issue、Git 提交或镜像层。

## 提交前检查

仓库忽略 `.env*` 实值文件，仅允许 `.env*.example` 模板。Docker 构建上下文也排除环境文件、运行时配置和本地验证产物。

```bash
git check-ignore .env .env.staging backend/.env frontend/.env.production
git diff --cached --name-only
gitleaks git . --log-opts=--all --redact=100
```

忽略规则不能撤销已有提交。如果历史中发现真实凭据，先停用或轮换，再单独安排历史清理；不要仅删除当前文件就认为旧提交不可见。
